from http.cookies import SimpleCookie

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, AuthSession, Role, User
from app.security import hash_password


def create_user(
    db: Session, role_name: str, email: str, password: str = "correct horse battery"
) -> User:
    role = db.scalar(select(Role).where(Role.name == role_name))
    assert role is not None
    user = User(
        email=email,
        full_name=role_name,
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    return user


def test_login_sets_opaque_http_only_session_and_csrf_cookie(client, db_session):
    create_user(db_session, "Owner", "owner@example.com")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "OWNER@example.com", "password": "correct horse battery"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    assert "mjd_session" in response.cookies
    assert "mjd_csrf" in response.cookies
    assert "httponly" in response.headers["set-cookie"].lower()
    parsed_cookies = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        parsed_cookies.load(header)
    assert parsed_cookies["mjd_session"]["path"] == "/api/v1"
    assert parsed_cookies["mjd_csrf"]["path"] == "/"
    session = db_session.scalar(select(AuthSession))
    assert session is not None
    assert session.token_hash != response.cookies["mjd_session"]
    assert session.csrf_token_hash != response.cookies["mjd_csrf"]


def test_authentication_requires_session_and_logout_requires_csrf(client, db_session):
    create_user(db_session, "Owner", "owner@example.com")
    assert client.get("/api/v1/auth/me").status_code == 401
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )

    rejected = client.post("/api/v1/auth/logout")
    assert rejected.status_code == 403
    csrf = client.cookies["mjd_csrf"]
    logged_out = client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})

    assert logged_out.status_code == 200
    assert db_session.scalar(select(AuthSession)) is None


def test_failed_password_is_generic_and_rate_limited(client, db_session):
    create_user(db_session, "Owner", "owner@example.com")
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "wrong password"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Email or password is incorrect."

    limited = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    assert limited.status_code == 429


def test_login_is_audited(client, db_session):
    create_user(db_session, "Owner", "owner@example.com")
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    entry = db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.login"))
    assert entry is not None


def test_password_change_invalidates_other_sessions_and_updates_credentials(client, db_session):
    user = create_user(db_session, "Owner", "owner@example.com")
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]
    assert (
        len(db_session.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all())
        == 2
    )

    changed = client.put(
        "/api/v1/auth/password",
        headers={"X-CSRF-Token": csrf},
        json={
            "current_password": "correct horse battery",
            "new_password": "a new correct horse battery",
        },
    )
    assert changed.status_code == 200
    assert (
        len(db_session.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all())
        == 1
    )

    current_csrf = client.cookies["mjd_csrf"]
    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": current_csrf})
    next_login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "a new correct horse battery"},
    )
    assert next_login.status_code == 200
