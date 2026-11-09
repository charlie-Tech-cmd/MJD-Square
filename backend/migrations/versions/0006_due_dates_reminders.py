"""Add invoice due dates, reminder activity, and transaction history indexes.

Revision ID: 0006_due_dates_reminders
Revises: 0005_account_payments
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_due_dates_reminders"
down_revision = "0005_account_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales", sa.Column("due_date", sa.Date(), nullable=True))
    op.execute("UPDATE sales SET due_date = sale_date WHERE due_date IS NULL")
    with op.batch_alter_table("sales") as batch_op:
        batch_op.alter_column("due_date", existing_type=sa.Date(), nullable=False)
    op.create_index("ix_sales_due_date", "sales", ["due_date"])

    op.create_table(
        "reminder_activities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "sale_id",
            sa.String(length=36),
            sa.ForeignKey("sales.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("channel", sa.String(length=20)),
        sa.Column("notes", sa.String(length=500), nullable=False),
        sa.Column(
            "created_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('prepared', 'sent_manually', 'follow_up_required', "
            "'promised_payment', 'disputed', 'resolved')",
            name="ck_reminder_activity_status_valid",
        ),
        sa.CheckConstraint(
            "channel IS NULL OR channel IN ('whatsapp', 'phone', 'in_person', 'other')",
            name="ck_reminder_activity_channel_valid",
        ),
    )
    op.create_index("ix_reminder_activities_sale_id", "reminder_activities", ["sale_id"])
    op.create_index(
        "ix_reminder_activities_created_by", "reminder_activities", ["created_by"]
    )


def downgrade() -> None:
    op.drop_index("ix_reminder_activities_created_by", table_name="reminder_activities")
    op.drop_index("ix_reminder_activities_sale_id", table_name="reminder_activities")
    op.drop_table("reminder_activities")
    op.drop_index("ix_sales_due_date", table_name="sales")
    with op.batch_alter_table("sales") as batch_op:
        batch_op.drop_column("due_date")
