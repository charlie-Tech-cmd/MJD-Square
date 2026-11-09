"""Add customer and supplier account payments.

Revision ID: 0005_account_payments
Revises: 0004_transactions
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_account_payments"
down_revision = "0004_transactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "customer_id",
            sa.String(length=36),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "supplier_id",
            sa.String(length=36),
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("reference", sa.String(length=100)),
        sa.Column("notes", sa.String(length=500), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_account_payment_amount_positive"),
        sa.CheckConstraint(
            "(customer_id IS NOT NULL AND supplier_id IS NULL) OR "
            "(customer_id IS NULL AND supplier_id IS NOT NULL)",
            name="ck_account_payment_single_account",
        ),
    )
    op.create_index("ix_account_payments_customer_id", "account_payments", ["customer_id"])
    op.create_index("ix_account_payments_supplier_id", "account_payments", ["supplier_id"])
    op.create_index("ix_account_payments_created_by", "account_payments", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_account_payments_created_by", table_name="account_payments")
    op.drop_index("ix_account_payments_supplier_id", table_name="account_payments")
    op.drop_index("ix_account_payments_customer_id", table_name="account_payments")
    op.drop_table("account_payments")
