"""Add customer WhatsApp receipt consent and delivery tracking.

Revision ID: 0008_whatsapp_payment_receipts
Revises: 0007_payment_evidence
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_whatsapp_payment_receipts"
down_revision = "0007_payment_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column(
            "whatsapp_receipt_opted_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "customers",
        sa.Column("whatsapp_receipt_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "whatsapp_receipts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "payment_id",
            sa.String(length=36),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            unique=True,
        ),
        sa.Column(
            "account_payment_id",
            sa.String(length=36),
            sa.ForeignKey("account_payments.id", ondelete="RESTRICT"),
            unique=True,
        ),
        sa.Column("customer_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("reference", sa.String(length=100)),
        sa.Column("transaction_reference", sa.String(length=100), nullable=False),
        sa.Column("balance_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider_message_id", sa.String(length=200), unique=True),
        sa.Column("failure_reason", sa.String(length=300)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(payment_id IS NOT NULL AND account_payment_id IS NULL) OR "
            "(payment_id IS NULL AND account_payment_id IS NOT NULL)",
            name="ck_whatsapp_receipt_single_payment",
        ),
        sa.CheckConstraint(
            "status IN ('not_opted_in', 'no_number', 'not_configured', 'pending', "
            "'invalid_number', "
            "'accepted', 'sent', 'delivered', 'read', 'failed')",
            name="ck_whatsapp_receipt_status_valid",
        ),
        sa.CheckConstraint("amount > 0", name="ck_whatsapp_receipt_amount_positive"),
        sa.CheckConstraint("balance_due >= 0", name="ck_whatsapp_receipt_balance_nonnegative"),
    )
    op.create_index("ix_whatsapp_receipts_status", "whatsapp_receipts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_whatsapp_receipts_status", table_name="whatsapp_receipts")
    op.drop_table("whatsapp_receipts")
    op.drop_column("customers", "whatsapp_receipt_consent_at")
    op.drop_column("customers", "whatsapp_receipt_opted_in")
