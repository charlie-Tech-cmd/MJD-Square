"""Add business records and inventory foundation.

Revision ID: 0003_business_records
Revises: 0002_password_recovery
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_business_records"
down_revision = "0002_password_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40)),
        sa.Column("whatsapp", sa.String(length=40)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("address", sa.String(length=500)),
        sa.Column("customer_type", sa.String(length=20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "customer_type IN ('retail', 'wholesale', 'both')",
            name="ck_customer_type_valid",
        ),
    )
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_table(
        "customer_opening_balances",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "customer_id",
            sa.String(length=36),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source_notes", sa.String(length=500), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_customer_opening_balance_positive"),
    )
    op.create_index(
        "ix_customer_opening_balances_customer_id",
        "customer_opening_balances",
        ["customer_id"],
    )
    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("contact_person", sa.String(length=160)),
        sa.Column("phone", sa.String(length=40)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("address", sa.String(length=500)),
        sa.Column("payment_terms_days", sa.Integer()),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "payment_terms_days IS NULL OR payment_terms_days >= 0",
            name="ck_supplier_payment_terms_nonnegative",
        ),
    )
    op.create_index("ix_suppliers_name", "suppliers", ["name"])
    op.create_table(
        "supplier_opening_balances",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source_notes", sa.String(length=500), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_supplier_opening_balance_positive"),
    )
    op.create_index(
        "ix_supplier_opening_balances_supplier_id",
        "supplier_opening_balances",
        ["supplier_id"],
    )
    op.create_table(
        "product_categories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "units_of_measure",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("abbreviation", sa.String(length=16), nullable=False, unique=True),
        sa.Column("decimal_places", sa.Integer(), nullable=False),
        sa.CheckConstraint("decimal_places BETWEEN 0 AND 3", name="ck_unit_decimal_places"),
    )
    op.bulk_insert(
        sa.table(
            "units_of_measure",
            sa.column("id", sa.String),
            sa.column("name", sa.String),
            sa.column("abbreviation", sa.String),
            sa.column("decimal_places", sa.Integer),
        ),
        [
            {"id": "piece", "name": "Piece", "abbreviation": "pc", "decimal_places": 0},
            {"id": "pack", "name": "Pack", "abbreviation": "pack", "decimal_places": 0},
            {"id": "carton", "name": "Carton", "abbreviation": "ctn", "decimal_places": 0},
            {"id": "bag", "name": "Bag", "abbreviation": "bag", "decimal_places": 0},
            {"id": "kilogram", "name": "Kilogram", "abbreviation": "kg", "decimal_places": 3},
            {"id": "litre", "name": "Litre", "abbreviation": "L", "decimal_places": 3},
        ],
    )
    op.create_table(
        "unit_conversions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "from_unit_id",
            sa.String(length=40),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_unit_id",
            sa.String(length=40),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("factor", sa.Numeric(14, 6), nullable=False),
        sa.UniqueConstraint("from_unit_id", "to_unit_id", name="uq_unit_conversion_pair"),
        sa.CheckConstraint("factor > 0", name="ck_unit_conversion_factor_positive"),
        sa.CheckConstraint("from_unit_id != to_unit_id", name="ck_unit_conversion_distinct"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False, unique=True),
        sa.Column("barcode", sa.String(length=80), unique=True),
        sa.Column(
            "category_id",
            sa.String(length=36),
            sa.ForeignKey("product_categories.id", ondelete="SET NULL"),
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "unit_id",
            sa.String(length=40),
            sa.ForeignKey("units_of_measure.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
        ),
        sa.Column("purchase_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("retail_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("wholesale_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("minimum_stock", sa.Numeric(14, 3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purchase_cost >= 0", name="ck_product_cost_nonnegative"),
        sa.CheckConstraint("retail_price >= 0", name="ck_product_retail_nonnegative"),
        sa.CheckConstraint("wholesale_price >= 0", name="ck_product_wholesale_nonnegative"),
        sa.CheckConstraint("minimum_stock >= 0", name="ck_product_minimum_stock_nonnegative"),
    )
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_supplier_id", "products", ["supplier_id"])
    op.create_table(
        "product_price_tiers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price_type", sa.String(length=20), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint(
            "product_id", "price_type", "minimum_quantity", name="uq_product_price_tier"
        ),
        sa.CheckConstraint(
            "price_type IN ('retail', 'wholesale')",
            name="ck_product_price_tier_type",
        ),
        sa.CheckConstraint("minimum_quantity > 0", name="ck_price_tier_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_price_tier_price_nonnegative"),
    )
    op.create_index("ix_product_price_tiers_product_id", "product_price_tiers", ["product_id"])
    op.create_table(
        "inventory_balances",
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity >= 0", name="ck_inventory_balance_nonnegative"),
    )
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("movement_type", sa.String(length=20), nullable=False),
        sa.Column("quantity_delta", sa.Numeric(14, 3), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity_delta != 0", name="ck_stock_movement_nonzero"),
        sa.CheckConstraint(
            "movement_type IN ('opening', 'adjustment', 'damage', 'purchase', 'sale', "
            "'customer_return', 'supplier_return')",
            name="ck_stock_movement_type",
        ),
    )
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])
    op.create_index("ix_stock_movements_created_by", "stock_movements", ["created_by"])

    op.execute(
        sa.text(
            "INSERT INTO permissions (id, description) VALUES "
            "('customers:opening_balance', 'Record documented customer opening balances.'), "
            "('suppliers:opening_balance', 'Record documented supplier opening balances.')"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT id, 'customers:opening_balance' FROM roles WHERE name = 'Owner'"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT id, 'suppliers:opening_balance' FROM roles WHERE name = 'Owner'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN "
            "('customers:opening_balance', 'suppliers:opening_balance')"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE id IN "
            "('customers:opening_balance', 'suppliers:opening_balance')"
        )
    )
    op.drop_index("ix_stock_movements_created_by", table_name="stock_movements")
    op.drop_index("ix_stock_movements_product_id", table_name="stock_movements")
    op.drop_table("stock_movements")
    op.drop_table("inventory_balances")
    op.drop_index("ix_product_price_tiers_product_id", table_name="product_price_tiers")
    op.drop_table("product_price_tiers")
    op.drop_index("ix_products_supplier_id", table_name="products")
    op.drop_index("ix_products_category_id", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
    op.drop_table("products")
    op.drop_table("unit_conversions")
    op.drop_table("units_of_measure")
    op.drop_table("product_categories")
    op.drop_index(
        "ix_supplier_opening_balances_supplier_id", table_name="supplier_opening_balances"
    )
    op.drop_table("supplier_opening_balances")
    op.drop_index("ix_suppliers_name", table_name="suppliers")
    op.drop_table("suppliers")
    op.drop_index(
        "ix_customer_opening_balances_customer_id", table_name="customer_opening_balances"
    )
    op.drop_table("customer_opening_balances")
    op.drop_index("ix_customers_name", table_name="customers")
    op.drop_table("customers")
