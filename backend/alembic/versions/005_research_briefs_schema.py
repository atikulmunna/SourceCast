"""Research briefs schema

Revision ID: 005_research_briefs_schema
Revises: 004_saved_insights_schema
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005_research_briefs_schema"
down_revision: str | None = "004_saved_insights_schema"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "research_briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=True),
        sa.Column("source_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(40), nullable=False, server_default="READY"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_briefs_user_id", "research_briefs", ["user_id"])
    op.create_index("idx_research_briefs_space_id", "research_briefs", ["space_id"])


def downgrade() -> None:
    op.drop_table("research_briefs")
