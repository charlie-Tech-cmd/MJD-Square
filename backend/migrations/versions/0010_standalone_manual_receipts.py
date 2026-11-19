"""Add standalone manual payment receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0010_standalone_manual_receipts"
down_revision = "0009_supplier_whatsapp_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manual_payment_receipts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("receipt_number", sa.String(length=40), nullable=False),
        sa.Column("business_name", sa.String(length=160), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payer_name", sa.String(length=160), nullable=False),
        sa.Column("payer_phone", sa.String(length=40)),
        sa.Column("purpose", sa.String(length=240), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_manual_payment_receipt_amount_positive"),
    )
    op.create_index(
        "ix_manual_payment_receipts_receipt_number",
        "manual_payment_receipts",
        ["receipt_number"],
        unique=True,
    )
    op.create_index(
        "ix_manual_payment_receipts_paid_on",
        "manual_payment_receipts",
        ["paid_on"],
    )
    op.create_index(
        "ix_manual_payment_receipts_created_by",
        "manual_payment_receipts",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_manual_payment_receipts_created_by", table_name="manual_payment_receipts")
    op.drop_index("ix_manual_payment_receipts_paid_on", table_name="manual_payment_receipts")
    op.drop_index(
        "ix_manual_payment_receipts_receipt_number",
        table_name="manual_payment_receipts",
    )
    op.drop_table("manual_payment_receipts")
