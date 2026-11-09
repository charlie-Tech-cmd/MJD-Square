from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AccountPayment,
    AuditLog,
    Customer,
    CustomerOpeningBalance,
    Expense,
    InventoryBalance,
    Payment,
    Product,
    Purchase,
    Role,
    Sale,
    StockMovement,
    Supplier,
    User,
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


def create_product(db: Session, *, stock: str = "10") -> Product:
    product = Product(
        name="Malt drink",
        sku="MALT-001",
        unit_id="piece",
        purchase_cost=Decimal("100.00"),
        retail_price=Decimal("200.00"),
        wholesale_price=Decimal("180.00"),
        minimum_stock=Decimal("2"),
        inventory_balance=InventoryBalance(quantity=Decimal(stock)),
    )
    db.add(product)
    db.commit()
    return product


def test_sale_updates_stock_and_records_partial_and_final_payments(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    product = create_product(db_session)
    csrf = sign_in(client, "owner@example.com")

    created = client.post(
        "/api/v1/sales",
        headers={"X-CSRF-Token": csrf},
        json={
            "sale_type": "retail",
            "sale_date": "2026-11-09",
            "lines": [{"product_id": product.id, "quantity": "2"}],
            "payment_amount": "100.00",
            "payment_method": "Cash",
        },
    )

    assert created.status_code == 201
    sale = created.json()
    assert sale["invoice_number"].startswith("INV-")
    assert sale["total_amount"] == "400.00"
    assert sale["amount_paid"] == "100.00"
    assert sale["balance_due"] == "300.00"
    assert sale["lines"][0]["unit_price"] == "200.00"
    assert db_session.get(InventoryBalance, product.id).quantity == Decimal("8.000")
    assert db_session.scalar(select(StockMovement).where(StockMovement.movement_type == "sale"))

    paid = client.post(
        f"/api/v1/sales/{sale['id']}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "300.00", "method": "POS", "reference": "POS-123"},
    )
    assert paid.status_code == 201
    refreshed = client.get(f"/api/v1/sales/{sale['id']}").json()
    assert refreshed["amount_paid"] == "400.00"
    assert refreshed["balance_due"] == "0.00"

    overpayment = client.post(
        f"/api/v1/sales/{sale['id']}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "0.01", "method": "Cash"},
    )
    assert overpayment.status_code == 409
    assert db_session.scalar(select(Payment).where(Payment.sale_id == sale["id"])).amount == (
        Decimal("100.00")
    )
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "sale.create"))


def test_sale_rejects_insufficient_stock_without_partial_changes(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    product = create_product(db_session, stock="1")
    csrf = sign_in(client, "owner@example.com")

    response = client.post(
        "/api/v1/sales",
        headers={"X-CSRF-Token": csrf},
        json={
            "sale_date": "2026-11-09",
            "lines": [{"product_id": product.id, "quantity": "2"}],
        },
    )

    assert response.status_code == 409
    assert db_session.get(InventoryBalance, product.id).quantity == Decimal("1.000")
    assert db_session.scalar(select(Sale)) is None
    assert db_session.scalar(select(StockMovement)) is None


def test_purchase_increases_stock_tracks_supplier_balance_and_records_expense(
    client, db_session: Session
):
    create_user(db_session, "Owner", "owner@example.com")
    product = create_product(db_session)
    supplier = Supplier(name="Lagos Wholesale")
    db_session.add(supplier)
    db_session.commit()
    csrf = sign_in(client, "owner@example.com")

    created = client.post(
        "/api/v1/purchases",
        headers={"X-CSRF-Token": csrf},
        json={
            "supplier_id": supplier.id,
            "supplier_reference": "SUP-459",
            "purchase_date": "2026-11-09",
            "lines": [{"product_id": product.id, "quantity": "5", "unit_cost": "125.00"}],
            "payment_amount": "200.00",
            "payment_method": "Bank transfer",
        },
    )

    assert created.status_code == 201
    purchase = created.json()
    assert purchase["purchase_number"].startswith("PUR-")
    assert purchase["total_amount"] == "625.00"
    assert purchase["balance_due"] == "425.00"
    assert db_session.get(InventoryBalance, product.id).quantity == Decimal("15.000")
    assert db_session.get(Product, product.id).purchase_cost == Decimal("125.00")
    assert db_session.scalar(select(Purchase).where(Purchase.id == purchase["id"]))
    assert db_session.scalar(select(StockMovement).where(StockMovement.movement_type == "purchase"))

    expense = client.post(
        "/api/v1/expenses",
        headers={"X-CSRF-Token": csrf},
        json={
            "category": "Transport",
            "description": "Delivery from supplier",
            "amount": "5000.00",
            "expense_date": "2026-11-09",
            "method": "Cash",
        },
    )
    assert expense.status_code == 201
    assert db_session.scalar(select(Expense).where(Expense.id == expense.json()["id"]))
    expense_audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "expense.create"))
    assert expense_audit is not None
    assert expense_audit.entity_id == expense.json()["id"]

    summary = client.get("/api/v1/reports/summary?from=2026-11-09&to=2026-11-09")
    assert summary.status_code == 200
    assert summary.json()["purchases_total"] == "625.00"
    assert summary.json()["payments_made"] == "200.00"
    assert summary.json()["expenses_total"] == "5000.00"
    outstanding = client.get("/api/v1/reports/outstanding")
    assert outstanding.status_code == 200
    supplier_balance = outstanding.json()["supplier_balances"][0]
    assert supplier_balance == {
        "id": supplier.id,
        "name": "Lagos Wholesale",
        "balance_due": "425.00",
    }
    supplier_payment = client.post(
        f"/api/v1/suppliers/{supplier.id}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "425.00", "method": "Cash", "reference": "SETTLE-1"},
    )
    assert supplier_payment.status_code == 201
    assert db_session.scalar(
        select(AccountPayment).where(AccountPayment.supplier_id == supplier.id)
    )
    assert client.get("/api/v1/reports/outstanding").json()["supplier_balances"] == []


def test_shop_staff_can_sell_but_cannot_manage_purchase_or_expense(client, db_session: Session):
    create_user(db_session, "Shop staff", "staff@example.com")
    product = create_product(db_session)
    csrf = sign_in(client, "staff@example.com")

    sale = client.post(
        "/api/v1/sales",
        headers={"X-CSRF-Token": csrf},
        json={
            "sale_date": date.today().isoformat(),
            "lines": [{"product_id": product.id, "quantity": "1"}],
        },
    )
    assert sale.status_code == 201

    purchase = client.get("/api/v1/purchases")
    assert purchase.status_code == 403
    expense = client.post(
        "/api/v1/expenses",
        headers={"X-CSRF-Token": csrf},
        json={
            "category": "Transport",
            "description": "Delivery",
            "amount": "10.00",
            "expense_date": date.today().isoformat(),
            "method": "Cash",
        },
    )
    assert expense.status_code == 403


def test_customer_balance_combines_opening_balance_sales_and_payments(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    product = create_product(db_session)
    customer = Customer(name="Corner shop", customer_type="retail")
    db_session.add(customer)
    db_session.flush()
    db_session.add(
        CustomerOpeningBalance(
            customer_id=customer.id,
            amount=Decimal("1000.00"),
            effective_date=date(2026, 11, 1),
            source_notes="Verified ledger balance",
        )
    )
    db_session.commit()
    csrf = sign_in(client, "owner@example.com")

    sale = client.post(
        "/api/v1/sales",
        headers={"X-CSRF-Token": csrf},
        json={
            "customer_id": customer.id,
            "sale_type": "retail",
            "sale_date": "2026-11-09",
            "lines": [{"product_id": product.id, "quantity": "1"}],
            "payment_amount": "50.00",
            "payment_method": "Cash",
        },
    )
    assert sale.status_code == 201
    outstanding = client.get("/api/v1/reports/outstanding")
    assert outstanding.status_code == 200
    assert outstanding.json()["customer_balances"] == [
        {"id": customer.id, "name": "Corner shop", "balance_due": "1150.00"}
    ]
    account_payment = client.post(
        f"/api/v1/customers/{customer.id}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "1000.00", "method": "Bank transfer", "reference": "CUST-101"},
    )
    assert account_payment.status_code == 201
    assert db_session.scalar(
        select(AccountPayment).where(AccountPayment.customer_id == customer.id)
    )
    assert client.get("/api/v1/reports/outstanding").json()["customer_balances"] == [
        {"id": customer.id, "name": "Corner shop", "balance_due": "150.00"}
    ]
    overpayment = client.post(
        f"/api/v1/customers/{customer.id}/payments",
        headers={"X-CSRF-Token": csrf},
        json={"amount": "150.01", "method": "Cash"},
    )
    assert overpayment.status_code == 409
    assert db_session.scalar(
        select(AccountPayment).where(AccountPayment.customer_id == customer.id)
    ).amount == Decimal("1000.00")
