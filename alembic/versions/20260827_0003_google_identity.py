"""Add optional Google identity fields to users.

Revision ID: 20260827_0003
Revises: 20260823_0002
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260827_0003"
down_revision = "20260823_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_subject", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("google_email", sa.String(length=320), nullable=True))
    op.create_index("ix_users_google_subject", "users", ["google_subject"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_google_subject", table_name="users")
    op.drop_column("users", "google_email")
    op.drop_column("users", "google_subject")
