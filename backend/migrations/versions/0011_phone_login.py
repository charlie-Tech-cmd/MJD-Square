"""Allow owner accounts to use a phone number without an email."""

import sqlalchemy as sa
from alembic import op

revision = "0011_phone_login"
down_revision = "0010_standalone_manual_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=320),
            nullable=True,
        )
        batch_op.add_column(sa.Column("phone", sa.String(length=40), nullable=True))
    op.create_index("ix_users_phone", "users", ["phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_phone", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("phone")
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=320),
            nullable=False,
        )
