from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, ManualPaymentReceipt, Role, User
from app.security import hash_password


def create_owner(db: Session) -> None:
    role = db.scalar(select(Role).where(Role.name == "Owner"))
    assert role is not None
    db.add(
        User(
            email="owner@example.com",
            full_name="Business Owner",
            password_hash=hash_password("correct horse battery"),
            role=role,
        )
    )
    db.commit()


def sign_in(client) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    return client.cookies["mjd_csrf"]


def test_manual_receipt_is_saved_listed_and_audited(client, db_session: Session):
    create_owner(db_session)
    csrf = sign_in(client)
    payload = {
        "payer_name": "  Ada Customer  ",
        "payer_phone": "+234 (801) 234-5678",
        "purpose": "Shop supplies",
        "amount": "1250.50",
        "payment_method": "cash",
        "paid_on": "2026-11-18",
    }

    created = client.post(
        "/api/v1/manual-receipts",
        headers={"X-CSRF-Token": csrf},
        json=payload,
    )

    assert created.status_code == 201
    receipt = created.json()
    assert receipt["payer_name"] == "Ada Customer"
    assert receipt["payer_phone"] == "+2348012345678"
    assert receipt["amount"] == "1250.50"
    assert receipt["payment_method"] == "Cash"
    assert receipt["business_name"] == "MJD Square"
    assert receipt["receipt_number"].startswith("MJD-20261118-")
    listing = client.get("/api/v1/manual-receipts")
    assert listing.status_code == 200
    assert listing.json()["receipts"][0]["id"] == receipt["id"]
    assert listing.json()["payment_methods"] == ["Cash", "POS", "Bank transfer"]
    assert (
        db_session.scalar(
            select(AuditLog).where(AuditLog.action == "manual_payment_receipt.create")
        )
        is not None
    )
    assert db_session.get(ManualPaymentReceipt, receipt["id"]) is not None


def test_manual_receipt_requires_csrf_and_configured_method(client, db_session: Session):
    create_owner(db_session)
    csrf = sign_in(client)
    payload = {
        "payer_name": "Ada Customer",
        "payer_phone": None,
        "purpose": "Shop supplies",
        "amount": "25.00",
        "payment_method": "Crypto",
        "paid_on": "2026-11-18",
    }

    no_csrf = client.post("/api/v1/manual-receipts", json=payload)
    assert no_csrf.status_code == 403

    invalid_method = client.post(
        "/api/v1/manual-receipts",
        headers={"X-CSRF-Token": csrf},
        json=payload,
    )
    assert invalid_method.status_code == 422
    assert db_session.scalar(select(ManualPaymentReceipt)) is None


def test_manual_receipt_requires_read_permission(client, db_session: Session):
    role = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert role is not None
    role.permissions = [
        permission for permission in role.permissions if permission.id != "payments:read"
    ]
    db_session.add(
        User(
            email="staff@example.com",
            full_name="Shop Staff",
            password_hash=hash_password("correct horse battery"),
            role=role,
        )
    )
    db_session.commit()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.com", "password": "correct horse battery"},
    )

    assert response.status_code == 200
    assert client.get("/api/v1/manual-receipts").status_code == 403
