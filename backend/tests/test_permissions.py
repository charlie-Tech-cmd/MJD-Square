from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Role, User
from app.security import hash_password


def test_shop_staff_cannot_change_business_settings(client, db_session: Session):
    role = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert role is not None
    user = User(
        email="staff@example.com",
        full_name="Shop staff",
        password_hash=hash_password("correct horse battery"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]

    response = client.put(
        "/api/v1/settings",
        headers={"X-CSRF-Token": csrf},
        json={
            "business_name": "Different business",
            "currency": "NGN",
            "timezone": "Africa/Lagos",
            "payment_methods": ["Cash"],
        },
    )

    assert response.status_code == 403


def test_owner_can_read_and_update_business_settings(client, db_session: Session):
    role = db_session.scalar(select(Role).where(Role.name == "Owner"))
    assert role is not None
    user = User(
        email="owner@example.com",
        full_name="Owner",
        password_hash=hash_password("correct horse battery"),
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    csrf = client.cookies["mjd_csrf"]
    payload = {
        "business_name": "MJD Square",
        "currency": "NGN",
        "timezone": "Africa/Lagos",
        "payment_methods": ["Cash", "POS", "Bank transfer"],
    }

    rejected = client.put("/api/v1/settings", json=payload)
    assert rejected.status_code == 403
    updated = client.put("/api/v1/settings", headers={"X-CSRF-Token": csrf}, json=payload)

    assert updated.status_code == 200
    assert updated.json()["currency"] == "NGN"
    assert client.get("/api/v1/settings").json()["business_name"] == "MJD Square"
