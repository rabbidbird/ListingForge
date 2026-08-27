"""Add first-touch acquisition attribution to users.

Revision ID: 20260827_0004
Revises: 20260827_0003
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260827_0004"
down_revision = "20260827_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("acquisition_source", sa.String(length=120)))
    op.add_column("users", sa.Column("acquisition_medium", sa.String(length=120)))
    op.add_column("users", sa.Column("acquisition_campaign", sa.String(length=120)))
    op.add_column("users", sa.Column("acquisition_content", sa.String(length=120)))
    op.add_column("users", sa.Column("acquisition_term", sa.String(length=120)))
    op.add_column("users", sa.Column("acquisition_landing_path", sa.String(length=200)))


def downgrade() -> None:
    op.drop_column("users", "acquisition_landing_path")
    op.drop_column("users", "acquisition_term")
    op.drop_column("users", "acquisition_content")
    op.drop_column("users", "acquisition_campaign")
    op.drop_column("users", "acquisition_medium")
    op.drop_column("users", "acquisition_source")
