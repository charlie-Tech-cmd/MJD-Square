"""Add sales, purchases, payments, and expenses.

Revision ID: 0004_transactions
Revises: 0003_business_records
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_transactions"
down_revision = "0003_business_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("invoice_number", sa.String(length=32), nullable=False, unique=True),
        sa.Column(
            "customer_id",
            sa.String(length=36),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
        ),
        sa.Column("sale_type", sa.String(length=20), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sale_type IN ('retail', 'wholesale')", name="ck_sale_type_valid"),
        sa.CheckConstraint("total_amount > 0", name="ck_sale_total_positive"),
    )
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])
    op.create_index("ix_sales_sale_date", "sales", ["sale_date"])
    op.create_index("ix_sales_created_by", "sales", ["created_by"])
    op.create_table(
        "sale_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "sale_id",
            sa.String(length=36),
            sa.ForeignKey("sales.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(length=160), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("unit_name", sa.String(length=80), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sale_line_quantity_positive"),
        sa.CheckConstraint("unit_price >= 0", name="ck_sale_line_price_nonnegative"),
        sa.CheckConstraint("line_total >= 0", name="ck_sale_line_total_nonnegative"),
    )
    op.create_index("ix_sale_lines_sale_id", "sale_lines", ["sale_id"])
    op.create_index("ix_sale_lines_product_id", "sale_lines", ["product_id"])
    op.create_table(
        "purchases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("purchase_number", sa.String(length=32), nullable=False, unique=True),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
        ),
        sa.Column("supplier_reference", sa.String(length=100)),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=False),
        sa.Column(
            "created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total_amount > 0", name="ck_purchase_total_positive"),
    )
    op.create_index("ix_purchases_supplier_id", "purchases", ["supplier_id"])
    op.create_index("ix_purchases_purchase_date", "purchases", ["purchase_date"])
    op.create_index("ix_purchases_created_by", "purchases", ["created_by"])
    op.create_table(
        "purchase_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "purchase_id",
            sa.String(length=36),
            sa.ForeignKey("purchases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(length=160), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("unit_name", sa.String(length=80), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_line_quantity_positive"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_purchase_line_cost_nonnegative"),
        sa.CheckConstraint("line_total >= 0", name="ck_purchase_line_total_nonnegative"),
    )
    op.create_index("ix_purchase_lines_purchase_id", "purchase_lines", ["purchase_id"])
    op.create_index("ix_purchase_lines_product_id", "purchase_lines", ["product_id"])
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "sale_id",
            sa.String(length=36),
            sa.ForeignKey("sales.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "purchase_id",
            sa.String(length=36),
            sa.ForeignKey("purchases.id", ondelete="RESTRICT"),
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("reference", sa.String(length=100)),
        sa.Column("notes", sa.String(length=500), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
        sa.CheckConstraint(
            "(sale_id IS NOT NULL AND purchase_id IS NULL) OR "
            "(sale_id IS NULL AND purchase_id IS NOT NULL)",
            name="ck_payment_single_allocation",
        ),
    )
    op.create_index("ix_payments_sale_id", "payments", ["sale_id"])
    op.create_index("ix_payments_purchase_id", "payments", ["purchase_id"])
    op.create_index("ix_payments_created_by", "payments", ["created_by"])
    op.create_table(
        "expenses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("reference", sa.String(length=100)),
        sa.Column("notes", sa.String(length=500), nullable=False),
        sa.Column(
            "created_by", sa.String(length=36), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_expense_amount_positive"),
    )
    op.create_index("ix_expenses_expense_date", "expenses", ["expense_date"])
    op.create_index("ix_expenses_created_by", "expenses", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_expenses_created_by", table_name="expenses")
    op.drop_index("ix_expenses_expense_date", table_name="expenses")
    op.drop_table("expenses")
    op.drop_index("ix_payments_created_by", table_name="payments")
    op.drop_index("ix_payments_purchase_id", table_name="payments")
    op.drop_index("ix_payments_sale_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_purchase_lines_product_id", table_name="purchase_lines")
    op.drop_index("ix_purchase_lines_purchase_id", table_name="purchase_lines")
    op.drop_table("purchase_lines")
    op.drop_index("ix_purchases_created_by", table_name="purchases")
    op.drop_index("ix_purchases_purchase_date", table_name="purchases")
    op.drop_index("ix_purchases_supplier_id", table_name="purchases")
    op.drop_table("purchases")
    op.drop_index("ix_sale_lines_product_id", table_name="sale_lines")
    op.drop_index("ix_sale_lines_sale_id", table_name="sale_lines")
    op.drop_table("sale_lines")
    op.drop_index("ix_sales_created_by", table_name="sales")
    op.drop_index("ix_sales_sale_date", table_name="sales")
    op.drop_index("ix_sales_customer_id", table_name="sales")
    op.drop_table("sales")
