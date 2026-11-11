from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccountPayment,
    AuditLog,
    InventoryBalance,
    Payment,
    PaymentEvidence,
    Product,
    Role,
    User,
)
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
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    return client.cookies["mjd_csrf"]


def create_paid_sale(client, db: Session, csrf: str) -> str:
    product = Product(
        name="Receipt test product",
        sku="RECEIPT-001",
        unit_id="piece",
        purchase_cost=Decimal("10.00"),
        retail_price=Decimal("20.00"),
        wholesale_price=Decimal("18.00"),
        inventory_balance=InventoryBalance(quantity=Decimal("5")),
    )
    db.add(product)
    db.commit()
    response = client.post(
        "/api/v1/sales",
        headers={"X-CSRF-Token": csrf},
        json={
            "sale_type": "retail",
            "sale_date": date.today().isoformat(),
            "lines": [{"product_id": product.id, "quantity": "1"}],
            "payment_amount": "10.00",
            "payment_method": "Cash",
        },
    )
    assert response.status_code == 201
    return response.json()["payments"][0]["id"]


def test_invoice_receipt_upload_is_persisted_audited_and_authorized(
    client, db_session: Session, monkeypatch
):
    create_owner(db_session)
    csrf = sign_in(client)
    payment_id = create_paid_sale(client, db_session, csrf)
    monkeypatch.setattr("app.receipt_storage.settings.s3_region", "test-region")
    monkeypatch.setattr("app.receipt_storage.settings.s3_bucket", "test-bucket")
    monkeypatch.setattr("app.receipt_storage.settings.s3_access_key_id", "test-access-key")
    monkeypatch.setattr(
        "app.receipt_storage.settings.s3_secret_access_key", "test-secret-key"
    )
    store = Mock()
    monkeypatch.setattr("app.api.payment_evidence.store_receipt", store)
    monkeypatch.setattr(
        "app.api.payment_evidence.receipt_download_url",
        lambda *args: "https://private.example/short-lived",
    )

    uploaded = client.post(
        f"/api/v1/payments/{payment_id}/receipts",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("../../transfer-proof.pdf", b"%PDF-1.7\nproof", "application/pdf")},
    )

    assert uploaded.status_code == 201
    evidence = uploaded.json()
    assert evidence["filename"] == "transfer-proof.pdf"
    assert evidence["content_type"] == "application/pdf"
    assert evidence["size_bytes"] == len(b"%PDF-1.7\nproof")
    assert db_session.get(PaymentEvidence, evidence["id"]).payment_id == payment_id
    assert db_session.scalar(
        select(AuditLog).where(AuditLog.action == "payment.evidence.upload")
    )
    store.assert_called_once()

    sale = client.get("/api/v1/sales").json()[0]
    assert sale["payments"][0]["receipts"][0]["id"] == evidence["id"]
    downloaded = client.get(
        f"/api/v1/payment-receipts/{evidence['id']}/download",
        follow_redirects=False,
    )
    assert downloaded.status_code == 307
    assert downloaded.headers["location"] == "https://private.example/short-lived"


def test_local_receipt_upload_and_download(client, db_session: Session, monkeypatch, tmp_path):
    create_owner(db_session)
    csrf = sign_in(client)
    payment_id = create_paid_sale(client, db_session, csrf)
    monkeypatch.setattr("app.receipt_storage.LOCAL_RECEIPT_STORAGE_DIR", tmp_path)
    monkeypatch.setattr("app.receipt_storage.settings.app_env", "development")
    for setting in (
        "s3_region",
        "s3_bucket",
        "s3_access_key_id",
        "s3_secret_access_key",
    ):
        monkeypatch.setattr(f"app.receipt_storage.settings.{setting}", None)

    uploaded = client.post(
        f"/api/v1/payments/{payment_id}/receipts",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("receipt.pdf", b"%PDF-1.7\nproof", "application/pdf")},
    )
    assert uploaded.status_code == 201

    downloaded = client.get(
        f"/api/v1/payment-receipts/{uploaded.json()['id']}/download",
        follow_redirects=False,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"%PDF-1.7\nproof"
    assert downloaded.headers["cache-control"] == "private, no-store"
    assert downloaded.headers["x-content-type-options"] == "nosniff"


def test_only_owner_can_remove_receipt_and_removal_is_audited(
    client, db_session: Session, monkeypatch
):
    create_owner(db_session)
    csrf = sign_in(client)
    payment_id = create_paid_sale(client, db_session, csrf)
    monkeypatch.setattr("app.api.payment_evidence.store_receipt", Mock())
    remove = Mock()
    monkeypatch.setattr("app.api.payment_evidence.remove_receipt", remove)
    uploaded = client.post(
        f"/api/v1/payments/{payment_id}/receipts",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("wrong-receipt.pdf", b"%PDF-1.7\nproof", "application/pdf")},
    )
    assert uploaded.status_code == 201
    receipt_id = uploaded.json()["id"]

    deleted = client.delete(
        f"/api/v1/payment-receipts/{receipt_id}",
        headers={"X-CSRF-Token": csrf},
    )

    assert deleted.status_code == 204
    assert db_session.scalar(
        select(PaymentEvidence).where(PaymentEvidence.id == receipt_id)
    ) is None
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "payment.evidence.delete",
            AuditLog.entity_id == receipt_id,
        )
    )
    assert audit is not None
    assert audit.actor_user_id is not None
    assert audit.details["filename"] == "wrong-receipt.pdf"
    remove.assert_called_once()


def test_non_owner_cannot_remove_receipts(client, db_session: Session):
    role = db_session.scalar(select(Role).where(Role.name == "Shop staff"))
    assert role is not None
    db_session.add(
        User(
            email="staff@example.com",
            full_name="Shop staff",
            password_hash=hash_password("correct horse battery"),
            role=role,
        )
    )
    db_session.commit()
    signed_in = client.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.com", "password": "correct horse battery"},
    )
    assert signed_in.status_code == 200
    csrf_token = client.cookies["mjd_csrf"]

    deleted = client.delete(
        "/api/v1/payment-receipts/not-a-receipt",
        headers={"X-CSRF-Token": csrf_token},
    )

    assert deleted.status_code == 403
    assert deleted.json()["detail"] == "Only Owners can remove payment receipts."


def test_rejects_bad_signatures_and_oversized_receipts(client, db_session: Session, monkeypatch):
    create_owner(db_session)
    csrf = sign_in(client)
    payment_id = create_paid_sale(client, db_session, csrf)
    store = Mock()
    monkeypatch.setattr("app.api.payment_evidence.store_receipt", store)

    unsupported = client.post(
        f"/api/v1/payments/{payment_id}/receipts",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("proof.pdf", b"not a PDF", "application/pdf")},
    )
    oversized = client.post(
        f"/api/v1/payments/{payment_id}/receipts",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("proof.pdf", b"%PDF-" + b"x" * (10 * 1024 * 1024), "application/pdf")},
    )

    assert unsupported.status_code == 415
    assert oversized.status_code == 413
    assert db_session.scalar(select(PaymentEvidence)) is None
    store.assert_not_called()


def test_account_receipt_upload_and_history(client, db_session: Session, monkeypatch):
    create_owner(db_session)
    csrf = sign_in(client)
    customer = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Receipt Customer",
            "opening_balance": "50.00",
            "opening_balance_date": date.today().isoformat(),
            "opening_balance_notes": "Opening balance for receipt test",
        },
    )
    assert customer.status_code == 201
    payment = client.post(
        f"/api/v1/customers/{customer.json()['id']}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "25.00", "method": "Bank transfer"},
    )
    assert payment.status_code == 201

    store = Mock()
    monkeypatch.setattr("app.api.payment_evidence.store_receipt", store)
    uploaded = client.post(
        f"/api/v1/account-payments/{payment.json()['id']}/receipts",
        headers={"X-CSRF-Token": csrf},
        files={"file": ("proof.png", b"\x89PNG\r\n\x1a\nproof", "image/png")},
    )
    assert uploaded.status_code == 201

    history = client.get("/api/v1/account-payments")
    assert history.status_code == 200
    assert history.json()[0]["account_type"] == "customer"
    assert history.json()[0]["account_name"] == "Receipt Customer"
    assert history.json()[0]["receipts"][0]["id"] == uploaded.json()["id"]
    assert db_session.get(AccountPayment, payment.json()["id"]) is not None


def test_upload_requires_csrf(client, db_session: Session):
    create_owner(db_session)
    sign_in(client)
    response = client.post(
        "/api/v1/payments/missing/receipts",
        files={"file": ("proof.pdf", b"%PDF-1.7\nproof", "application/pdf")},
    )
    assert response.status_code == 403
    assert db_session.scalar(select(Payment)) is None
