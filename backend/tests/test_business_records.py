from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    Customer,
    CustomerOpeningBalance,
    Product,
    Role,
    Supplier,
    SupplierOpeningBalance,
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


def test_owner_can_create_customers_and_document_opening_balances(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    csrf = sign_in(client, "owner@example.com")

    created = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "  Adebayo Stores  ",
            "phone": "+2348000000000",
            "whatsapp": "+2348000000000",
            "email": "buyer@example.com",
            "customer_type": "wholesale",
            "opening_balance": "125000.25",
            "opening_balance_date": "2026-10-31",
            "opening_balance_notes": "Closing balance from the paper ledger",
        },
    )

    assert created.status_code == 201
    customer_id = created.json()["id"]
    assert created.json()["name"] == "Adebayo Stores"
    assert Decimal(created.json()["opening_balance_total"]) == Decimal("125000.25")
    assert created.json()["opening_balances"][0]["source_notes"] == (
        "Closing balance from the paper ledger"
    )
    assert db_session.scalar(
        select(CustomerOpeningBalance).where(CustomerOpeningBalance.customer_id == customer_id)
    )
    customer = db_session.get(Customer, customer_id)
    assert customer is not None and customer.customer_type == "wholesale"

    updated = client.patch(
        f"/api/v1/customers/{customer_id}",
        headers={"X-CSRF-Token": csrf},
        json={"phone": "+2348111111111", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+2348111111111"
    assert updated.json()["is_active"] is False
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "customer.update"))


def test_owner_can_create_customer_without_email(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    csrf = sign_in(client, "owner@example.com")

    created = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": csrf},
        json={"name": "Walk-in customer"},
    )

    assert created.status_code == 201
    assert created.json()["email"] is None


def test_shop_staff_cannot_record_opening_balances(client, db_session: Session):
    create_user(db_session, "Shop staff", "staff@example.com")
    csrf = sign_in(client, "staff@example.com")

    response = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Walk-in customer",
            "opening_balance": "50.00",
            "opening_balance_date": "2026-11-01",
            "opening_balance_notes": "Migrated balance",
        },
    )

    assert response.status_code == 403
    assert db_session.scalar(select(Customer)) is None


def test_owner_can_create_suppliers_and_document_opening_payables(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    csrf = sign_in(client, "owner@example.com")

    created = client.post(
        "/api/v1/suppliers",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Lagos Wholesale",
            "contact_person": "Ibrahim",
            "payment_terms_days": 30,
            "opening_balance": "75000.00",
            "opening_balance_date": "2026-10-31",
            "opening_balance_notes": "Supplier statement carried forward",
        },
    )

    assert created.status_code == 201
    supplier_id = created.json()["id"]
    assert Decimal(created.json()["opening_balance_total"]) == Decimal("75000.00")
    assert db_session.scalar(
        select(SupplierOpeningBalance).where(SupplierOpeningBalance.supplier_id == supplier_id)
    )
    assert db_session.get(Supplier, supplier_id) is not None


def test_product_creation_and_stock_adjustments_are_audited_and_atomic(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    csrf = sign_in(client, "owner@example.com")
    category = client.post(
        "/api/v1/product-categories",
        headers={"X-CSRF-Token": csrf},
        json={"name": "Drinks"},
    )
    assert category.status_code == 201

    created = client.post(
        "/api/v1/products",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Malt drink",
            "sku": " malt-001 ",
            "category_id": category.json()["id"],
            "unit_id": "piece",
            "purchase_cost": "120.25",
            "retail_price": "200.00",
            "wholesale_price": "180.00",
            "minimum_stock": "3",
            "opening_stock": "10",
            "opening_stock_reason": "Counted during setup",
            "price_tiers": [
                {"price_type": "wholesale", "minimum_quantity": "12", "unit_price": "170.00"}
            ],
        },
    )
    assert created.status_code == 201
    product = created.json()
    assert product["sku"] == "MALT-001"
    assert product["stock_quantity"] == "10.000"
    assert product["is_low_stock"] is False
    assert product["price_tiers"][0]["unit_price"] == "170.00"

    damage = client.post(
        f"/api/v1/products/{product['id']}/stock-movements",
        headers={"X-CSRF-Token": csrf},
        json={
            "movement_type": "damage",
            "quantity_delta": "-2",
            "reason": "Two bottles were damaged",
        },
    )
    assert damage.status_code == 201
    refreshed = client.get("/api/v1/products").json()[0]
    assert refreshed["stock_quantity"] == "8.000"

    insufficient = client.post(
        f"/api/v1/products/{product['id']}/stock-movements",
        headers={"X-CSRF-Token": csrf},
        json={
            "movement_type": "adjustment",
            "quantity_delta": "-9",
            "reason": "Invalid count",
        },
    )
    assert insufficient.status_code == 409
    assert client.get("/api/v1/products").json()[0]["stock_quantity"] == "8.000"
    movements = client.get(f"/api/v1/products/{product['id']}/stock-movements")
    assert movements.status_code == 200
    assert len(movements.json()) == 2
    assert db_session.scalar(select(AuditLog).where(AuditLog.action == "inventory.stock_movement"))
    assert db_session.get(Product, product["id"]) is not None


def test_staff_can_read_but_not_manage_inventory(client, db_session: Session):
    create_user(db_session, "Shop staff", "staff@example.com")
    csrf = sign_in(client, "staff@example.com")

    assert client.get("/api/v1/products").status_code == 200
    denied = client.post(
        "/api/v1/products",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Restricted item",
            "sku": "restricted-1",
            "unit_id": "piece",
            "purchase_cost": "1.00",
            "retail_price": "2.00",
            "wholesale_price": "1.50",
        },
    )
    assert denied.status_code == 403


def test_product_unit_precision_and_unit_change_are_protected(client, db_session: Session):
    create_user(db_session, "Owner", "owner@example.com")
    csrf = sign_in(client, "owner@example.com")
    invalid_precision = client.post(
        "/api/v1/products",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Single piece",
            "sku": "piece-precision",
            "unit_id": "piece",
            "purchase_cost": "1.00",
            "retail_price": "2.00",
            "wholesale_price": "1.50",
            "opening_stock": "1.5",
            "opening_stock_reason": "Opening count",
        },
    )
    assert invalid_precision.status_code == 422

    product = client.post(
        "/api/v1/products",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "Piece item",
            "sku": "piece-unit",
            "unit_id": "piece",
            "purchase_cost": "1.00",
            "retail_price": "2.00",
            "wholesale_price": "1.50",
            "opening_stock": "2",
            "opening_stock_reason": "Opening count",
        },
    )
    assert product.status_code == 201
    changed = client.patch(
        f"/api/v1/products/{product.json()['id']}",
        headers={"X-CSRF-Token": csrf},
        json={"unit_id": "kilogram"},
    )
    assert changed.status_code == 409
