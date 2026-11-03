from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, AuthSession, Role, User
from app.security import hash_password


def create_owner(db: Session) -> None:
    role = db.scalar(select(Role).where(Role.name == "Owner"))
    assert role is not None
    db.add(
        User(
            email="owner@example.com",
            full_name="Owner",
            password_hash=hash_password("correct horse battery"),
            role=role,
        )
    )
    db.commit()


def sign_in(client) -> str:
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    return client.cookies["mjd_csrf"]


def test_owner_can_create_list_and_deactivate_staff(client, db_session: Session):
    create_owner(db_session)
    csrf = sign_in(client)
    response = client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "email": "staff@example.com",
            "full_name": "Shop Staff",
            "password": "a longer staff password",
        },
    )
    assert response.status_code == 201
    staff_id = response.json()["id"]
    assert response.json()["role"]["name"] == "Shop staff"

    listed = client.get("/api/v1/users")
    assert listed.status_code == 200
    assert {user["email"] for user in listed.json()} == {"owner@example.com", "staff@example.com"}

    client.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.com", "password": "a longer staff password"},
    )
    assert db_session.scalar(select(AuthSession).where(AuthSession.user_id == staff_id)) is not None
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]
    removed = client.delete(f"/api/v1/users/{staff_id}", headers={"X-CSRF-Token": csrf})

    assert removed.status_code == 204
    staff = db_session.get(User, staff_id)
    assert staff is not None and not staff.is_active
    assert db_session.scalar(select(AuthSession).where(AuthSession.user_id == staff_id)) is None
    assert (
        db_session.scalar(select(AuditLog).where(AuditLog.action == "user.deactivate")) is not None
    )


def test_staff_cannot_manage_users(client, db_session: Session):
    staff_role = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert staff_role is not None
    db_session.add(
        User(
            email="staff@example.com",
            full_name="Shop Staff",
            password_hash=hash_password("correct horse battery"),
            role=staff_role,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]

    response = client.post(
        "/api/v1/users",
        headers={"X-CSRF-Token": csrf},
        json={
            "email": "another@example.com",
            "full_name": "Another",
            "password": "a longer staff password",
        },
    )

    assert response.status_code == 403
