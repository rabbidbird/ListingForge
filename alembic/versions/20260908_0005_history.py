"""Add the composite listing-history keyset index.

Revision ID: 20260908_0005_history
Revises: 20260827_0004
"""

from __future__ import annotations

from alembic import op

revision = "20260908_0005_history"
down_revision = "20260827_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_listings_user_created_id",
        "listings",
        ["user_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_listings_user_created_id", table_name="listings")
