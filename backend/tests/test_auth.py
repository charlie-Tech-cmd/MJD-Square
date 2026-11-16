from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    AuthSession,
    LoginAttempt,
    PasswordResetAttempt,
    PasswordResetToken,
    Role,
    User,
)
from app.security import hash_password, token_digest, verify_password


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


def request_password_reset(client, email: str):
    return client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )


def test_forgot_password_response_is_generic_and_token_is_hashed(client, db_session, monkeypatch):
    user = create_user(db_session, "Owner", "owner@example.com")
    sent_emails = []

    def capture_email(recipient: str, reset_url: str) -> None:
        sent_emails.append((recipient, reset_url))

    monkeypatch.setattr("app.api.auth.send_password_reset_email", capture_email)

    unknown = request_password_reset(client, "unknown@example.com")
    eligible = request_password_reset(client, "owner@example.com")

    assert unknown.status_code == eligible.status_code == 200
    assert unknown.json() == eligible.json()
    assert unknown.json()["message"] == (
        "If an eligible account exists, password reset instructions will be sent."
    )
    assert len(sent_emails) == 1
    assert sent_emails[0][0] == user.email

    raw_token = parse_qs(urlparse(sent_emails[0][1]).query)["token"][0]
    stored_token = db_session.scalar(select(PasswordResetToken))

    assert stored_token is not None
    assert stored_token.user_id == user.id
    assert stored_token.token_hash == token_digest(raw_token)
    assert stored_token.token_hash != raw_token
    assert stored_token.used_at is None


def test_password_reset_updates_password_and_revokes_all_sessions(client, db_session, monkeypatch):
    user = create_user(db_session, "Owner", "owner@example.com")
    for _ in range(2):
        login = client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "correct horse battery"},
        )
        assert login.status_code == 200

    sessions_before = db_session.scalars(
        select(AuthSession).where(AuthSession.user_id == user.id)
    ).all()
    assert len(sessions_before) == 2

    sent_emails = []
    monkeypatch.setattr(
        "app.api.auth.send_password_reset_email",
        lambda recipient, reset_url: sent_emails.append((recipient, reset_url)),
    )

    requested = request_password_reset(client, user.email)
    assert requested.status_code == 200
    raw_token = parse_qs(urlparse(sent_emails[0][1]).query)["token"][0]

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "another secure horse battery",
        },
    )

    assert reset.status_code == 200
    assert reset.json() == {"status": "password_updated"}
    db_session.refresh(user)
    assert verify_password("another secure horse battery", user.password_hash)
    assert db_session.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all() == []

    reset_record = db_session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_digest(raw_token))
    )
    assert reset_record is not None
    assert reset_record.used_at is not None

    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.password_reset"))
    assert audit is not None
    assert audit.actor_user_id == user.id

    assert client.get("/api/v1/auth/me").status_code == 401

    next_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "another secure horse battery",
        },
    )
    assert next_login.status_code == 200


def test_password_reset_token_cannot_be_reused(client, db_session, monkeypatch):
    user = create_user(db_session, "Owner", "owner@example.com")
    sent_emails = []
    monkeypatch.setattr(
        "app.api.auth.send_password_reset_email",
        lambda recipient, reset_url: sent_emails.append(reset_url),
    )

    request_password_reset(client, user.email)
    raw_token = parse_qs(urlparse(sent_emails[0]).query)["token"][0]
    payload = {
        "token": raw_token,
        "new_password": "another secure horse battery",
    }

    first = client.post("/api/v1/auth/reset-password", json=payload)
    second = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "a different secure horse battery",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 400
    assert second.json()["detail"] == ("This password reset link is invalid or has expired.")


def test_expired_password_reset_token_is_rejected(client, db_session):
    user = create_user(db_session, "Owner", "owner@example.com")
    raw_token = "expired-test-token-value-123456789"
    db_session.add(
        PasswordResetToken(
            token_hash=token_digest(raw_token),
            user_id=user.id,
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw_token,
            "new_password": "another secure horse battery",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == ("This password reset link is invalid or has expired.")
    db_session.refresh(user)
    assert verify_password("correct horse battery", user.password_hash)


def test_forgot_password_is_rate_limited_per_ip_without_revealing_accounts(client, db_session):
    responses = [
        request_password_reset(client, f"unknown-{index}@example.com") for index in range(6)
    ]

    assert all(response.status_code == 200 for response in responses)
    assert len({response.json()["message"] for response in responses}) == 1
    assert db_session.query(PasswordResetAttempt).count() == 6


def test_forgot_password_limits_reset_tokens_per_account(client, db_session, monkeypatch):
    user = create_user(db_session, "Owner", "owner@example.com")
    sent_emails = []
    monkeypatch.setattr(
        "app.api.auth.send_password_reset_email",
        lambda recipient, reset_url: sent_emails.append(reset_url),
    )

    responses = [request_password_reset(client, user.email) for _ in range(4)]

    assert all(response.status_code == 200 for response in responses)
    assert len(sent_emails) == 3
    assert db_session.query(PasswordResetToken).filter_by(user_id=user.id).count() == 3


def test_forgot_password_ignores_expired_tokens_when_counting_active_reset_tokens(
    client, db_session, monkeypatch
):
    user = create_user(db_session, "Owner", "owner@example.com")
    sent_emails = []
    monkeypatch.setattr(
        "app.api.auth.send_password_reset_email",
        lambda recipient, reset_url: sent_emails.append(reset_url),
    )

    db_session.add_all(
        [
            PasswordResetToken(
                token_hash=token_digest(f"expired-token-{index}"),
                user_id=user.id,
                expires_at=datetime.now(UTC) - timedelta(minutes=5),
                created_at=datetime.now(UTC) - timedelta(minutes=10),
            )
            for index in range(3)
        ]
    )
    db_session.commit()

    response = request_password_reset(client, user.email)

    assert response.status_code == 200
    assert len(sent_emails) == 1
    assert db_session.query(PasswordResetToken).filter_by(user_id=user.id).count() == 4


def test_forgot_password_does_not_send_email_for_inactive_user(client, db_session, monkeypatch):
    user = create_user(db_session, "Owner", "inactive@example.com")
    user.is_active = False
    db_session.commit()
    sent_emails = []
    monkeypatch.setattr(
        "app.api.auth.send_password_reset_email",
        lambda recipient, reset_url: sent_emails.append(reset_url),
    )

    response = request_password_reset(client, user.email)

    assert response.status_code == 200
    assert response.json()["message"] == (
        "If an eligible account exists, password reset instructions will be sent."
    )
    assert sent_emails == []
    assert db_session.query(PasswordResetToken).filter_by(user_id=user.id).count() == 0



def test_login_accepts_legacy_short_password(client, db_session):
    create_user(db_session, "Owner", "legacy@example.com", password="x")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy@example.com", "password": "x"},
    )

    assert response.status_code == 200


def test_password_change_rejects_password_shorter_than_12_characters(
    client, db_session
):
    create_user(db_session, "Owner", "owner@example.com")
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )

    response = client.put(
        "/api/v1/auth/password",
        headers={"X-CSRF-Token": client.cookies["mjd_csrf"]},
        json={
            "current_password": "correct horse battery",
            "new_password": "12345678901",
        },
    )

    assert response.status_code == 422


def test_password_reset_rejects_password_shorter_than_12_characters(client):
    response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "valid-looking-reset-token-123",
            "new_password": "12345678901",
        },
    )

    assert response.status_code == 422


def test_login_removes_old_attempts_and_preserves_recent_attempts(
    client, db_session
):
    old_attempt = LoginAttempt(
        email="old@example.com",
        client_ip="192.0.2.1",
        succeeded=False,
        occurred_at=datetime.now(UTC) - timedelta(days=2),
    )
    recent_attempt = LoginAttempt(
        email="owner@example.com",
        client_ip="testclient",
        succeeded=False,
        occurred_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add_all([old_attempt, recent_attempt])
    db_session.commit()
    old_id = old_attempt.id
    recent_id = recent_attempt.id

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong password"},
    )

    assert response.status_code == 401
    db_session.expire_all()
    assert db_session.get(LoginAttempt, old_id) is None
    assert db_session.get(LoginAttempt, recent_id) is not None


def test_login_cleanup_is_committed_when_rate_limited(client, db_session):
    create_user(db_session, "Owner", "owner@example.com")

    old_attempt = LoginAttempt(
        email="old@example.com",
        client_ip="192.0.2.1",
        succeeded=False,
        occurred_at=datetime.now(UTC) - timedelta(days=2),
    )
    db_session.add(old_attempt)

    for _ in range(5):
        db_session.add(
            LoginAttempt(
                email="owner@example.com",
                client_ip="testclient",
                succeeded=False,
                occurred_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )

    db_session.commit()
    old_id = old_attempt.id

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com",
              "password": "correct horse battery"},
    )

    assert response.status_code == 429
    db_session.expire_all()
    assert db_session.get(LoginAttempt, old_id) is None
    assert (
        db_session.query(LoginAttempt)
        .filter(
            LoginAttempt.email == "owner@example.com",
            LoginAttempt.succeeded.is_(False),
        )
        .count()
        == 5
    )
