"""Add supplier WhatsApp consent and payment direction to receipts.

Revision ID: 0009_supplier_whatsapp_payments
Revises: 0008_whatsapp_payment_receipts
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_supplier_whatsapp_payments"
down_revision = "0008_whatsapp_payment_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("suppliers", sa.Column("whatsapp", sa.String(length=40), nullable=True))
    op.add_column(
        "suppliers",
        sa.Column(
            "whatsapp_receipt_opted_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "suppliers",
        sa.Column("whatsapp_receipt_consent_at", sa.DateTime(timezone=True), nullable=True),
    )
    with op.batch_alter_table("whatsapp_receipts") as batch_op:
        batch_op.alter_column("customer_name", new_column_name="recipient_name")
        batch_op.add_column(
            sa.Column(
                "recipient_kind",
                sa.String(length=16),
                nullable=True,
                server_default="customer",
            )
        )
        batch_op.add_column(
            sa.Column(
                "payment_direction",
                sa.String(length=16),
                nullable=True,
                server_default="received",
            )
        )
        batch_op.alter_column(
            "recipient_kind",
            existing_type=sa.String(length=16),
            nullable=False,
            server_default=None,
        )
        batch_op.alter_column(
            "payment_direction",
            existing_type=sa.String(length=16),
            nullable=False,
            server_default=None,
        )
        batch_op.create_check_constraint(
            "ck_whatsapp_receipt_recipient_kind_valid",
            "recipient_kind IN ('customer', 'supplier')",
        )
        batch_op.create_check_constraint(
            "ck_whatsapp_receipt_direction_valid",
            "payment_direction IN ('received', 'paid')",
        )


def downgrade() -> None:
    with op.batch_alter_table("whatsapp_receipts") as batch_op:
        batch_op.drop_constraint("ck_whatsapp_receipt_direction_valid", type_="check")
        batch_op.drop_constraint("ck_whatsapp_receipt_recipient_kind_valid", type_="check")
        batch_op.drop_column("payment_direction")
        batch_op.drop_column("recipient_kind")
        batch_op.alter_column("recipient_name", new_column_name="customer_name")
    op.drop_column("suppliers", "whatsapp_receipt_consent_at")
    op.drop_column("suppliers", "whatsapp_receipt_opted_in")
    op.drop_column("suppliers", "whatsapp")
