"""add membership level to users

Revision ID: 20250921_1200
Revises: 20250822_0715_cfce8e7fd052_add_multitenant_support_to_users
Create Date: 2025-09-21 14:50:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250921_1200"
down_revision = "20250822_0715_cfce8e7fd052_add_multitenant_support_to_users"
branch_labels = None
depends_on = None


membership_enum = sa.Enum(
    "free",
    "pro",
    "enterprise",
    name="membership_level",
)


def upgrade() -> None:
    bind = op.get_bind()
    membership_enum.create(bind, checkfirst=True)
    op.add_column(
        "users",
        sa.Column(
            "membership_level",
            membership_enum,
            nullable=False,
            server_default="free",
        ),
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN membership_level DROP DEFAULT"
    )


def downgrade() -> None:
    op.drop_column("users", "membership_level")
    bind = op.get_bind()
    membership_enum.drop(bind, checkfirst=True)
