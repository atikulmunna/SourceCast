"""Initial Phase 1 schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-05-23

Creates:
- users
- refresh_tokens
- knowledge_spaces
- sources
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("role", sa.String(40), nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("idx_users_email", "users", ["email"])

    # ── refresh_tokens ─────────────────────────────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    # ── knowledge_spaces ────────────────────────────────────────────────────────
    op.create_table(
        "knowledge_spaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_knowledge_spaces_user_name"),
    )
    op.create_index("idx_knowledge_spaces_user_id", "knowledge_spaces", ["user_id"])

    # ── sources ────────────────────────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_url", sa.Text, nullable=False),
        sa.Column("canonical_url", sa.Text, nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("creator_name", sa.String(255), nullable=True),
        sa.Column("thumbnail_url", sa.Text, nullable=True),
        sa.Column("duration_sec", sa.Integer, nullable=True),
        sa.Column("publish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(20), nullable=False, server_default="auto"),
        sa.Column("status", sa.String(40), nullable=False, server_default="PENDING"),
        sa.Column(
            "transcript_status",
            sa.String(40),
            nullable=False,
            server_default="NOT_STARTED",
        ),
        sa.Column(
            "indexing_status",
            sa.String(40),
            nullable=False,
            server_default="NOT_STARTED",
        ),
        sa.Column("audio_file_url", sa.Text, nullable=True),
        sa.Column(
            "audio_storage_policy",
            sa.String(50),
            nullable=False,
            server_default="DELETE_AFTER_TRANSCRIPTION",
        ),
        sa.Column("audio_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "canonical_url", name="uq_sources_user_canonical_url"
        ),
    )
    op.create_index("idx_sources_user_id", "sources", ["user_id"])
    op.create_index("idx_sources_status", "sources", ["status"])


def downgrade() -> None:
    op.drop_table("sources")
    op.drop_table("knowledge_spaces")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
