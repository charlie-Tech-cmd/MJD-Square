import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from urllib.error import URLError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Customer,
    InventoryBalance,
    Payment,
    Product,
    Purchase,
    Role,
    Sale,
    User,
    WhatsAppReceipt,
)
from app.security import hash_password


class FakeResponse:
    def __init__(self, message_id: str):
        self.message_id = message_id

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return json.dumps({"messages": [{"id": self.message_id}]}).encode()


def create_owner(db: Session) -> None:
    role = db.scalar(select(Role).where(Role.name == "Owner"))
    assert role is not None
    db.add(
        User(
            email="wa-owner@example.com",
            full_name="Owner",
            password_hash=hash_password("correct horse battery"),
            role=role,
        )
    )
    db.commit()


def configure_whatsapp(monkeypatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "whatsapp_access_token", "test-token")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123456789")
    monkeypatch.setattr(settings, "whatsapp_api_version", "v23.0")
    monkeypatch.setattr(settings, "whatsapp_receipt_template", "payment_receipt")
    monkeypatch.setattr(settings, "whatsapp_receipt_template_language", "en")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "test-app-secret")
    monkeypatch.setattr(settings, "whatsapp_webhook_verify_token", "test-verify-token")


def csrf_for(client) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wa-owner@example.com", "password": "correct horse battery"},
    )
    assert response.status_code == 200
    return client.cookies["mjd_csrf"]


def sign_webhook(body: bytes) -> str:
    digest = hmac.new(b"test-app-secret", body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@contextmanager
def _test_session(db: Session):
    yield db


def test_sale_payment_sends_opted_in_whatsapp_receipt_and_tracks_delivery(
    client, db_session: Session, monkeypatch
):
    configure_whatsapp(monkeypatch)
    sent_requests = []

    def fake_urlopen(request, timeout):
        sent_requests.append((request, timeout))
        return FakeResponse(f"wamid.test-message-{len(sent_requests)}")

    monkeypatch.setattr("app.whatsapp_service.urlopen", fake_urlopen)
    create_owner(db_session)
    customer_response = client.post(
        "/api/v1/customers",
        json={
            "name": "Ada Stores",
            "whatsapp": "+234 800 000 0000",
            "whatsapp_receipt_opted_in": True,
        },
        headers={"X-CSRF-Token": csrf_for(client)},
    )
    assert customer_response.status_code == 201
    customer = customer_response.json()
    assert customer["whatsapp_receipt_opted_in"] is True
    assert customer["whatsapp_receipt_consent_at"] is not None

    product = Product(
        name="Malt drink",
        sku="MALT-WA",
        unit_id="piece",
        purchase_cost=Decimal("100"),
        retail_price=Decimal("200"),
        wholesale_price=Decimal("180"),
        minimum_stock=Decimal("1"),
        inventory_balance=InventoryBalance(quantity=Decimal("10")),
    )
    db_session.add(product)
    db_session.commit()
    csrf = client.cookies["mjd_csrf"]

    sale_response = client.post(
        "/api/v1/sales",
        headers={"X-CSRF-Token": csrf},
        json={
            "customer_id": customer["id"],
            "sale_type": "retail",
            "sale_date": date.today().isoformat(),
            "lines": [{"product_id": product.id, "quantity": "2"}],
            "payment_amount": "100.00",
            "payment_method": "Cash",
        },
    )

    assert sale_response.status_code == 201
    sale = sale_response.json()
    assert sale["payments"][0]["whatsapp_receipt_status"] == "accepted"
    assert len(sent_requests) == 1
    request, timeout = sent_requests[0]
    assert request.full_url == "https://graph.facebook.com/v23.0/123456789/messages"
    assert request.get_header("Authorization") == "Bearer test-token"
    assert timeout == 10
    message = json.loads(request.data)
    assert message["to"] == "2348000000000"
    assert len(message["template"]["components"][0]["parameters"]) == 11

    receipt = db_session.scalar(select(WhatsAppReceipt))
    assert receipt is not None
    assert receipt.transaction_reference == sale["invoice_number"]
    assert receipt.amount == Decimal("100.00")
    assert receipt.balance_due == Decimal("300.00")
    assert receipt.provider_message_id == "wamid.test-message-1"
    assert receipt.status == "accepted"

    challenge = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "challenge-value",
        },
    )
    assert challenge.status_code == 200
    assert challenge.text == "challenge-value"
    monkeypatch.setattr(
        "app.api.whatsapp.SessionLocal",
        lambda: _test_session(db_session),
    )

    webhook_body = json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [
                                    {
                                        "id": "wamid.test-message-1",
                                        "status": "delivered",
                                        "timestamp": "1790000000",
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    ).encode()
    webhook_response = client.post(
        "/webhooks/whatsapp",
        content=webhook_body,
        headers={"X-Hub-Signature-256": sign_webhook(webhook_body)},
    )
    assert webhook_response.status_code == 200
    assert webhook_response.json()["updated"] == 1
    db_session.refresh(receipt)
    assert receipt.status == "delivered"
    assert receipt.delivered_at is not None

    account_payment_response = client.post(
        f"/api/v1/customers/{customer['id']}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "50.00", "method": "Cash", "reference": "ACCOUNT-1"},
    )
    assert account_payment_response.status_code == 201
    assert account_payment_response.json()["whatsapp_receipt_status"] == "accepted"
    account_receipt = db_session.scalar(
        select(WhatsAppReceipt).where(WhatsAppReceipt.account_payment_id.is_not(None))
    )
    assert account_receipt is not None
    assert account_receipt.transaction_reference == "Customer account"
    assert len(sent_requests) == 2

    wrong_signature = client.post(
        "/webhooks/whatsapp",
        content=webhook_body,
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert wrong_signature.status_code == 403

    update = client.patch(
        f"/api/v1/customers/{customer['id']}",
        headers={"X-CSRF-Token": csrf},
        json={"whatsapp": "+2348111111111"},
    )
    assert update.status_code == 200
    assert update.json()["whatsapp_receipt_opted_in"] is False
    assert update.json()["whatsapp_receipt_consent_at"] is None
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "customer.update"))


def test_supplier_invoice_and_account_payments_send_opted_in_confirmations(
    client, db_session: Session, monkeypatch
):
    configure_whatsapp(monkeypatch)
    sent_requests = []

    def fake_urlopen(request, timeout):
        sent_requests.append((request, timeout))
        return FakeResponse(f"wamid.supplier-{len(sent_requests)}")

    monkeypatch.setattr("app.whatsapp_service.urlopen", fake_urlopen)
    create_owner(db_session)
    csrf = csrf_for(client)
    supplier_response = client.post(
        "/api/v1/suppliers",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Lagos Wholesale",
            "whatsapp": "+234 800 111 2222",
            "whatsapp_receipt_opted_in": True,
            "opening_balance": "50.00",
            "opening_balance_date": date.today().isoformat(),
            "opening_balance_notes": "Supplier statement",
        },
    )
    assert supplier_response.status_code == 201
    supplier = supplier_response.json()
    assert supplier["whatsapp_receipt_opted_in"] is True
    assert supplier["whatsapp_receipt_consent_at"] is not None

    product = Product(
        name="Malt drink",
        sku="MALT-SUPPLIER-WA",
        unit_id="piece",
        purchase_cost=Decimal("100"),
        retail_price=Decimal("200"),
        wholesale_price=Decimal("180"),
        minimum_stock=Decimal("1"),
        inventory_balance=InventoryBalance(quantity=Decimal("10")),
    )
    db_session.add(product)
    db_session.commit()

    purchase_response = client.post(
        "/api/v1/purchases",
        headers={"X-CSRF-Token": csrf},
        json={
            "supplier_id": supplier["id"],
            "purchase_date": date.today().isoformat(),
            "lines": [{"product_id": product.id, "quantity": "1", "unit_cost": "100.00"}],
            "payment_amount": "20.00",
            "payment_method": "Cash",
        },
    )
    assert purchase_response.status_code == 201
    purchase = purchase_response.json()
    assert purchase["payments"][0]["whatsapp_receipt_status"] == "accepted"
    first_receipt = db_session.scalar(select(WhatsAppReceipt))
    assert first_receipt is not None
    assert first_receipt.recipient_kind == "supplier"
    assert first_receipt.recipient_name == "Lagos Wholesale"
    assert first_receipt.payment_direction == "paid"
    assert first_receipt.transaction_reference == purchase["purchase_number"]
    first_parameters = json.loads(sent_requests[0][0].data)["template"]["components"][0][
        "parameters"
    ]
    assert first_parameters[2]["text"] == "payment made by MJD Square to you"
    assert first_parameters[0]["text"] == "Lagos Wholesale"

    invoice_payment = client.post(
        f"/api/v1/purchases/{purchase['id']}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "80.00", "method": "Bank transfer", "reference": "SUP-INV-2"},
    )
    assert invoice_payment.status_code == 201
    assert invoice_payment.json()["whatsapp_receipt_status"] == "accepted"

    account_payment = client.post(
        f"/api/v1/suppliers/{supplier['id']}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "25.00", "method": "Cash", "reference": "SUP-ACCT-1"},
    )
    assert account_payment.status_code == 201
    assert account_payment.json()["whatsapp_receipt_status"] == "accepted"
    assert len(sent_requests) == 3
    assert db_session.scalar(select(Purchase).where(Purchase.id == purchase["id"]))
    assert len(db_session.scalars(select(WhatsAppReceipt)).all()) == 3

    update = client.patch(
        f"/api/v1/suppliers/{supplier['id']}",
        headers={"X-CSRF-Token": csrf},
        json={"whatsapp": "+2348111111111"},
    )
    assert update.status_code == 200
    assert update.json()["whatsapp_receipt_opted_in"] is False
    assert update.json()["whatsapp_receipt_consent_at"] is None


def test_payment_is_saved_when_whatsapp_delivery_fails(client, db_session: Session, monkeypatch):
    configure_whatsapp(monkeypatch)

    def failed_urlopen(*_args, **_kwargs):
        raise URLError("connection failed")

    monkeypatch.setattr("app.whatsapp_service.urlopen", failed_urlopen)
    create_owner(db_session)
    csrf = csrf_for(client)
    customer = Customer(
        name="Opted-in customer",
        whatsapp="2348000000000",
        whatsapp_receipt_opted_in=True,
    )
    db_session.add(customer)
    product = Product(
        name="Malt drink",
        sku="MALT-FAIL-WA",
        unit_id="piece",
        purchase_cost=Decimal("100"),
        retail_price=Decimal("200"),
        wholesale_price=Decimal("180"),
        minimum_stock=Decimal("1"),
        inventory_balance=InventoryBalance(quantity=Decimal("10")),
    )
    db_session.add(product)
    db_session.commit()

    response = client.post(
        "/api/v1/sales",
        headers={"X-CSRF-Token": csrf},
        json={
            "customer_id": customer.id,
            "sale_type": "retail",
            "sale_date": date.today().isoformat(),
            "lines": [{"product_id": product.id, "quantity": "1"}],
            "payment_amount": "50.00",
            "payment_method": "Cash",
        },
    )

    assert response.status_code == 201
    assert response.json()["payments"][0]["whatsapp_receipt_status"] == "failed"
    assert db_session.scalar(select(Sale).where(Sale.id == response.json()["id"]))
    assert db_session.scalar(select(Payment).where(Payment.sale_id == response.json()["id"]))
    receipt = db_session.scalar(select(WhatsAppReceipt))
    assert receipt is not None and receipt.failure_reason
