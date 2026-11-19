from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_id",
        String(80),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions, lazy="selectin"
    )


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    description: Mapped[str] = mapped_column(String(200), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    role: Mapped[Role] = relationship(lazy="joined")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    user: Mapped[User] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class BusinessSettings(Base):
    __tablename__ = "business_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    business_name: Mapped[str] = mapped_column(String(160), nullable=False, default="MJD Square")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Lagos")
    payment_methods: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=lambda: ["Cash", "POS", "Bank transfer"]
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    actor: Mapped[User | None] = relationship()


class ReminderActivity(Base):
    __tablename__ = "reminder_activities"
    __table_args__ = (
        CheckConstraint(
            "status IN ('prepared', 'sent_manually', 'follow_up_required', "
            "'promised_payment', 'disputed', 'resolved')",
            name="ck_reminder_activity_status_valid",
        ),
        CheckConstraint(
            "channel IS NULL OR channel IN ('whatsapp', 'phone', 'in_person', 'other')",
            name="ck_reminder_activity_channel_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sale_id: Mapped[str] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    actor: Mapped[User | None] = relationship()


class SystemEvent(Base):
    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PasswordResetAttempt(Base):
    __tablename__ = "password_reset_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        CheckConstraint(
            "customer_type IN ('retail', 'wholesale', 'both')", name="ck_customer_type_valid"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    whatsapp: Mapped[str | None] = mapped_column(String(40))
    whatsapp_receipt_opted_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    whatsapp_receipt_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str | None] = mapped_column(String(500))
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False, default="retail")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CustomerOpeningBalance(Base):
    __tablename__ = "customer_opening_balances"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_customer_opening_balance_positive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_notes: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint(
            "payment_terms_days IS NULL OR payment_terms_days >= 0",
            name="ck_supplier_payment_terms_nonnegative",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    contact_person: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40))
    whatsapp: Mapped[str | None] = mapped_column(String(40))
    whatsapp_receipt_opted_in: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    whatsapp_receipt_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str | None] = mapped_column(String(500))
    payment_terms_days: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SupplierOpeningBalance(Base):
    __tablename__ = "supplier_opening_balances"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_supplier_opening_balance_positive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_notes: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UnitOfMeasure(Base):
    __tablename__ = "units_of_measure"
    __table_args__ = (
        CheckConstraint("decimal_places BETWEEN 0 AND 3", name="ck_unit_decimal_places"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, default=3)


class UnitConversion(Base):
    __tablename__ = "unit_conversions"
    __table_args__ = (
        UniqueConstraint("from_unit_id", "to_unit_id", name="uq_unit_conversion_pair"),
        CheckConstraint("factor > 0", name="ck_unit_conversion_factor_positive"),
        CheckConstraint("from_unit_id != to_unit_id", name="ck_unit_conversion_distinct"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    from_unit_id: Mapped[str] = mapped_column(
        ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    to_unit_id: Mapped[str] = mapped_column(
        ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    factor: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("purchase_cost >= 0", name="ck_product_cost_nonnegative"),
        CheckConstraint("retail_price >= 0", name="ck_product_retail_nonnegative"),
        CheckConstraint("wholesale_price >= 0", name="ck_product_wholesale_nonnegative"),
        CheckConstraint("minimum_stock >= 0", name="ck_product_minimum_stock_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(80), unique=True)
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    unit_id: Mapped[str] = mapped_column(
        ForeignKey("units_of_measure.id", ondelete="RESTRICT"), nullable=False
    )
    supplier_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    retail_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    wholesale_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    minimum_stock: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    category: Mapped[ProductCategory | None] = relationship(lazy="selectin")
    unit: Mapped[UnitOfMeasure] = relationship(lazy="selectin")
    supplier: Mapped[Supplier | None] = relationship(lazy="selectin")
    price_tiers: Mapped[list["ProductPriceTier"]] = relationship(
        cascade="all, delete-orphan", order_by="ProductPriceTier.minimum_quantity"
    )
    inventory_balance: Mapped["InventoryBalance | None"] = relationship(
        cascade="all, delete-orphan", uselist=False
    )


class ProductPriceTier(Base):
    __tablename__ = "product_price_tiers"
    __table_args__ = (
        UniqueConstraint(
            "product_id", "price_type", "minimum_quantity", name="uq_product_price_tier"
        ),
        CheckConstraint(
            "price_type IN ('retail', 'wholesale')",
            name="ck_product_price_tier_type",
        ),
        CheckConstraint("minimum_quantity > 0", name="ck_price_tier_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_price_tier_price_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    price_type: Mapped[str] = mapped_column(String(20), nullable=False)
    minimum_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class InventoryBalance(Base):
    __tablename__ = "inventory_balances"
    __table_args__ = (CheckConstraint("quantity >= 0", name="ck_inventory_balance_nonnegative"),)

    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint("quantity_delta != 0", name="ck_stock_movement_nonzero"),
        CheckConstraint(
            "movement_type IN ('opening', 'adjustment', 'damage', 'purchase', "
            "'sale', 'customer_return', 'supplier_return')",
            name="ck_stock_movement_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PaymentEvidence(Base):
    __tablename__ = "payment_evidence"
    __table_args__ = (
        CheckConstraint(
            "(payment_id IS NOT NULL AND account_payment_id IS NULL) OR "
            "(payment_id IS NULL AND account_payment_id IS NOT NULL)",
            name="ck_payment_evidence_single_payment",
        ),
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 10485760",
            name="ck_payment_evidence_size_limit",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    account_payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("account_payments.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    object_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    uploaded_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    payment: Mapped["Payment | None"] = relationship(back_populates="receipts")
    account_payment: Mapped["AccountPayment | None"] = relationship(back_populates="receipts")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("sale_type IN ('retail', 'wholesale')", name="ck_sale_type_valid"),
        CheckConstraint("total_amount > 0", name="ck_sale_total_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    sale_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    customer: Mapped[Customer | None] = relationship(lazy="joined")
    lines: Mapped[list["SaleLine"]] = relationship(
        cascade="all, delete-orphan", order_by="SaleLine.id", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(
        cascade="all, delete-orphan", order_by="Payment.received_at", lazy="selectin"
    )


class SaleLine(Base):
    __tablename__ = "sale_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_sale_line_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_sale_line_price_nonnegative"),
        CheckConstraint("line_total >= 0", name="ck_sale_line_total_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sale_id: Mapped[str] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (CheckConstraint("total_amount > 0", name="ck_purchase_total_positive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    purchase_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    supplier_reference: Mapped[str | None] = mapped_column(String(100))
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    notes: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    supplier: Mapped[Supplier | None] = relationship(lazy="joined")
    lines: Mapped[list["PurchaseLine"]] = relationship(
        cascade="all, delete-orphan", order_by="PurchaseLine.id", lazy="selectin"
    )
    payments: Mapped[list["Payment"]] = relationship(
        cascade="all, delete-orphan", order_by="Payment.received_at", lazy="selectin"
    )


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_purchase_line_quantity_positive"),
        CheckConstraint("unit_cost >= 0", name="ck_purchase_line_cost_nonnegative"),
        CheckConstraint("line_total >= 0", name="ck_purchase_line_total_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    purchase_id: Mapped[str] = mapped_column(
        ForeignKey("purchases.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    sku: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_name: Mapped[str] = mapped_column(String(80), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        CheckConstraint(
            "(sale_id IS NOT NULL AND purchase_id IS NULL) OR "
            "(sale_id IS NULL AND purchase_id IS NOT NULL)",
            name="ck_payment_single_allocation",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    purchase_id: Mapped[str | None] = mapped_column(
        ForeignKey("purchases.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    receipts: Mapped[list["PaymentEvidence"]] = relationship(
        back_populates="payment", order_by="PaymentEvidence.uploaded_at", lazy="selectin"
    )
    whatsapp_receipt: Mapped["WhatsAppReceipt | None"] = relationship(
        back_populates="payment", uselist=False, lazy="selectin"
    )

    @property
    def whatsapp_receipt_status(self) -> str | None:
        return self.whatsapp_receipt.status if self.whatsapp_receipt else None


class AccountPayment(Base):
    __tablename__ = "account_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_account_payment_amount_positive"),
        CheckConstraint(
            "(customer_id IS NOT NULL AND supplier_id IS NULL) OR "
            "(customer_id IS NULL AND supplier_id IS NOT NULL)",
            name="ck_account_payment_single_account",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    supplier_id: Mapped[str | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    receipts: Mapped[list["PaymentEvidence"]] = relationship(
        back_populates="account_payment",
        order_by="PaymentEvidence.uploaded_at",
        lazy="selectin",
    )
    whatsapp_receipt: Mapped["WhatsAppReceipt | None"] = relationship(
        back_populates="account_payment", uselist=False, lazy="selectin"
    )

    @property
    def whatsapp_receipt_status(self) -> str | None:
        return self.whatsapp_receipt.status if self.whatsapp_receipt else None


class ManualPaymentReceipt(Base):
    __tablename__ = "manual_payment_receipts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_manual_payment_receipt_amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    receipt_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(160), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payer_name: Mapped[str] = mapped_column(String(160), nullable=False)
    payer_phone: Mapped[str | None] = mapped_column(String(40))
    purpose: Mapped[str] = mapped_column(String(240), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(40), nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WhatsAppReceipt(Base):
    __tablename__ = "whatsapp_receipts"
    __table_args__ = (
        CheckConstraint(
            "(payment_id IS NOT NULL AND account_payment_id IS NULL) OR "
            "(payment_id IS NULL AND account_payment_id IS NOT NULL)",
            name="ck_whatsapp_receipt_single_payment",
        ),
        CheckConstraint(
            "status IN ('not_opted_in', 'no_number', 'not_configured', 'pending', "
            "'invalid_number', 'accepted', 'sent', 'delivered', 'read', 'failed')",
            name="ck_whatsapp_receipt_status_valid",
        ),
        CheckConstraint("amount > 0", name="ck_whatsapp_receipt_amount_positive"),
        CheckConstraint("balance_due >= 0", name="ck_whatsapp_receipt_balance_nonnegative"),
        CheckConstraint(
            "recipient_kind IN ('customer', 'supplier')",
            name="ck_whatsapp_receipt_recipient_kind_valid",
        ),
        CheckConstraint(
            "payment_direction IN ('received', 'paid')",
            name="ck_whatsapp_receipt_direction_valid",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), unique=True
    )
    account_payment_id: Mapped[str | None] = mapped_column(
        ForeignKey("account_payments.id", ondelete="RESTRICT"), unique=True
    )
    recipient_name: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="customer")
    payment_direction: Mapped[str] = mapped_column(String(16), nullable=False, default="received")
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    transaction_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    balance_due: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    failure_reason: Mapped[str | None] = mapped_column(String(300))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    payment: Mapped[Payment | None] = relationship(back_populates="whatsapp_receipt")
    account_payment: Mapped[AccountPayment | None] = relationship(
        back_populates="whatsapp_receipt"
    )


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_expense_amount_positive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(40), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
