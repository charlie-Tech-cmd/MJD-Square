from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Customer,
    InventoryBalance,
    Product,
    ReminderActivity,
    Role,
    User,
    utc_now,
)
from app.security import hash_password


def create_user(db: Session, role_name: str, email: str) -> User:
    role = db.scalar(select(Role).where(Role.name == role_name))
    assert role is not None
    user = User(
        email=email,
        full_name=role_name,
        password_hash=hash_password("correct horse battery"),
        role=role,
    )
    db.add(user)
    db.commit()
    return user


def sign_in(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct horse battery"},
    )
    assert response.status_code == 200
    return client.cookies["mjd_csrf"]


def create_sale(client, csrf: str, db: Session, *, due_date: str | None = None):
    customer = Customer(name="Ada Customer", phone="08012345678")
    product = Product(
        name="Malt drink",
        sku=f"MALT-{uuid4().hex[:8]}",
        unit_id="piece",
        purchase_cost=Decimal("100.00"),
        retail_price=Decimal("200.00"),
        wholesale_price=Decimal("180.00"),
        minimum_stock=Decimal("2"),
        inventory_balance=InventoryBalance(quantity=Decimal("10")),
    )
    db.add_all([customer, product])
    db.commit()
    today = utc_now().astimezone(ZoneInfo("Africa/Lagos")).date()
    sale_date = today - timedelta(days=3)
    payload = {
        "customer_id": customer.id,
        "sale_type": "retail",
        "sale_date": sale_date.isoformat(),
        "lines": [{"product_id": product.id, "quantity": "1"}],
    }
    if due_date is not None:
        payload["due_date"] = due_date
    response = client.post("/api/v1/sales", headers={"X-CSRF-Token": csrf}, json=payload)
    return response, customer


def test_due_date_defaults_to_sale_date_and_cannot_precede_it(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    csrf = sign_in(client, "owner@example.com")
    today = utc_now().astimezone(ZoneInfo("Africa/Lagos")).date()

    created, _ = create_sale(client, csrf, db_session)
    assert created.status_code == 201
    assert created.json()["due_date"] == created.json()["sale_date"]

    invalid, _ = create_sale(
        client,
        csrf,
        db_session,
        due_date=(today - timedelta(days=4)).isoformat(),
    )
    assert invalid.status_code == 422


def test_payment_reminders_track_manual_activity_and_appear_in_history(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    csrf = sign_in(client, "owner@example.com")
    today = utc_now().astimezone(ZoneInfo("Africa/Lagos")).date()

    created, customer = create_sale(
        client,
        csrf,
        db_session,
        due_date=(today - timedelta(days=2)).isoformat(),
    )
    assert created.status_code == 201
    sale = created.json()

    reminders = client.get("/api/v1/payment-reminders")
    assert reminders.status_code == 200
    reminder = reminders.json()[0]
    assert reminder["invoice_number"] == sale["invoice_number"]
    assert reminder["customer_id"] == customer.id
    assert reminder["balance_due"] == "200.00"
    assert reminder["days_overdue"] == 2
    assert reminder["latest_status"] is None

    activity = client.post(
        f"/api/v1/sales/{sale['id']}/reminder-activities",
        headers={"X-CSRF-Token": csrf},
        json={"status": "sent_manually", "channel": "whatsapp", "notes": "Sent after review."},
    )
    assert activity.status_code == 201
    assert activity.json()["status"] == "sent_manually"
    assert db_session.scalar(select(ReminderActivity).where(ReminderActivity.sale_id == sale["id"]))
    assert db_session.scalar(
        select(AuditLog).where(AuditLog.action == "payment_reminder.activity")
    )

    updated = client.get("/api/v1/payment-reminders").json()[0]
    assert updated["latest_status"] == "sent_manually"
    assert updated["last_contacted_at"] is not None
    assert updated["activities"][0]["notes"] == "Sent after review."

    history = client.get("/api/v1/transaction-history")
    assert history.status_code == 200
    assert {entry["action"] for entry in history.json()} >= {
        "sale.create",
        "payment_reminder.activity",
    }
    invoice_search = client.get(
        f"/api/v1/transaction-history?q={sale['invoice_number']}"
    )
    assert invoice_search.status_code == 200
    assert {entry["action"] for entry in invoice_search.json()} >= {
        "sale.create",
        "payment_reminder.activity",
    }


def test_transaction_history_is_owner_only_but_staff_can_record_reminder_activity(
    client, db_session: Session
):
    create_user(db_session, "Owner", "owner@example.com")
    owner_csrf = sign_in(client, "owner@example.com")
    created, _ = create_sale(client, owner_csrf, db_session)
    sale_id = created.json()["id"]

    client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": owner_csrf})
    create_user(db_session, "Shop staff", "staff@example.com")
    staff_csrf = sign_in(client, "staff@example.com")

    assert client.get("/api/v1/payment-reminders").status_code == 200
    assert client.get("/api/v1/transaction-history").status_code == 403
    activity = client.post(
        f"/api/v1/sales/{sale_id}/reminder-activities",
        headers={"X-CSRF-Token": staff_csrf},
        json={"status": "prepared", "notes": "Call tomorrow."},
    )
    assert activity.status_code == 201
