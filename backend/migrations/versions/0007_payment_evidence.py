"""Store uploaded payment receipt metadata.

Revision ID: 0007_payment_evidence
Revises: 0006_due_dates_reminders
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_payment_evidence"
down_revision = "0006_due_dates_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_evidence",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "payment_id",
            sa.String(length=36),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "account_payment_id",
            sa.String(length=36),
            sa.ForeignKey("account_payments.id", ondelete="RESTRICT"),
        ),
        sa.Column("object_key", sa.String(length=500), nullable=False, unique=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "uploaded_by_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.CheckConstraint(
            "(payment_id IS NOT NULL AND account_payment_id IS NULL) OR "
            "(payment_id IS NULL AND account_payment_id IS NOT NULL)",
            name="ck_payment_evidence_single_payment",
        ),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 10485760",
            name="ck_payment_evidence_size_limit",
        ),
    )
    op.create_index("ix_payment_evidence_payment_id", "payment_evidence", ["payment_id"])
    op.create_index(
        "ix_payment_evidence_account_payment_id",
        "payment_evidence",
        ["account_payment_id"],
    )
    op.create_index(
        "ix_payment_evidence_uploaded_by_id", "payment_evidence", ["uploaded_by_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_payment_evidence_uploaded_by_id", table_name="payment_evidence")
    op.drop_index(
        "ix_payment_evidence_account_payment_id", table_name="payment_evidence"
    )
    op.drop_index("ix_payment_evidence_payment_id", table_name="payment_evidence")
    op.drop_table("payment_evidence")
