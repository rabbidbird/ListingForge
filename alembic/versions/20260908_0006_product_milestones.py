"""Content-free unique milestones and explicit fixture classification.

Revision ID: 20260908_0006
Revises: 20260908_0005
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260908_0006"
down_revision = "20260908_0005_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_test_fixture", sa.Boolean(), nullable=True),
    )
    op.create_table(
        "product_milestones",
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.Column("is_backfilled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Preserve already observed first drafts; never infer payments or returns.
    op.execute(
        sa.text("""
        INSERT INTO product_milestones (user_id, kind, created_at, is_backfilled)
        SELECT user_id, kind, MIN(created_at), true FROM usage_events
        WHERE kind = 'first_draft_generated' AND status = 'completed'
        GROUP BY user_id, kind
    """)
    )


def downgrade() -> None:
    op.drop_table("product_milestones")
    op.drop_column("users", "is_test_fixture")
