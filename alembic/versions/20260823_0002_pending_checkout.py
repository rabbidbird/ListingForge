"""Persist one open Stripe Checkout session per user.

Revision ID: 20260823_0002
Revises: 20260815_0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260823_0002"
down_revision = "20260815_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("pending_checkout_session_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("pending_checkout_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("pending_checkout_plan", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column(
            "pending_checkout_expires_at",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_index(
        "uq_subscriptions_pending_checkout_session_id",
        "subscriptions",
        ["pending_checkout_session_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_subscriptions_pending_checkout_session_id",
        table_name="subscriptions",
    )
    op.drop_column("subscriptions", "pending_checkout_expires_at")
    op.drop_column("subscriptions", "pending_checkout_plan")
    op.drop_column("subscriptions", "pending_checkout_url")
    op.drop_column("subscriptions", "pending_checkout_session_id")
