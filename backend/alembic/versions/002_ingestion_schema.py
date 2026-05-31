"""Phase 2 ingestion schema

Revision ID: 002_ingestion_schema
Revises: 001_initial_schema
Create Date: 2026-05-24

Creates:
- embedding_models        (no external FKs — must come first)
- source_spaces           (FK: sources, knowledge_spaces, users)
- ingestion_jobs          (FK: users, sources)
- transcript_segments     (FK: sources, users)
- transcript_chunks       (FK: sources, users, knowledge_spaces, embedding_models)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_ingestion_schema"
down_revision: str | None = "001_initial_schema"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:

    # ── embedding_models ────────────────────────────────────────────────────
    # Created first; transcript_chunks has a FK to this table.
    op.create_table(
        "embedding_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=False),
        sa.Column("distance_metric", sa.String(40), nullable=False, server_default="Cosine"),
        sa.Column("qdrant_collection", sa.String(160), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "dimensions", name="uq_embedding_models_name_dims"),
    )

    # Seed the default MVP model so workers can look it up by name
    op.execute(
        """
        INSERT INTO embedding_models (id, name, provider, dimensions, distance_metric,
                                      qdrant_collection, is_active)
        VALUES (gen_random_uuid(),
                'all-MiniLM-L6-v2',
                'sentence-transformers',
                384,
                'Cosine',
                'source_chunks_v1_minilm_384',
                true)
        """
    )

    # ── source_spaces ───────────────────────────────────────────────────────
    op.create_table(
        "source_spaces",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id", "space_id"),
    )
    op.create_index("idx_source_spaces_space_id", "source_spaces", ["space_id"])
    op.create_index("idx_source_spaces_user_id", "source_spaces", ["user_id"])

    # ── ingestion_jobs ──────────────────────────────────────────────────────
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "job_type",
            sa.String(60),
            nullable=False,
            server_default="SOURCE_INGESTION",
        ),
        sa.Column("worker_task_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="PENDING"),
        sa.Column("stage", sa.String(80), nullable=True),
        sa.Column("progress", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current_step", sa.Text, nullable=True),
        sa.Column("estimated_seconds_remaining", sa.Integer, nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default="3"),
        sa.Column(
            "logs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ingestion_jobs_user_id", "ingestion_jobs", ["user_id"])
    op.create_index("idx_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])
    op.create_index("idx_ingestion_jobs_status", "ingestion_jobs", ["status"])

    # ── transcript_segments ─────────────────────────────────────────────────
    op.create_table(
        "transcript_segments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_index", sa.Integer, nullable=False),
        sa.Column("start_time_sec", sa.Numeric(10, 3), nullable=False),
        sa.Column("end_time_sec", sa.Numeric(10, 3), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("speaker_label", sa.String(80), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "segment_index",
            name="uq_transcript_segments_source_index",
        ),
    )
    op.create_index("idx_transcript_segments_source_id", "transcript_segments", ["source_id"])
    op.create_index("idx_transcript_segments_user_id", "transcript_segments", ["user_id"])
    op.create_index(
        "idx_transcript_segments_source_time",
        "transcript_segments",
        ["source_id", "start_time_sec"],
    )

    # ── transcript_chunks ───────────────────────────────────────────────────
    op.create_table(
        "transcript_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("start_time_sec", sa.Numeric(10, 3), nullable=False),
        sa.Column("end_time_sec", sa.Numeric(10, 3), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("embedding_model_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("vector_collection", sa.String(160), nullable=False, server_default=""),
        sa.Column("vector_point_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["knowledge_spaces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["embedding_model_id"], ["embedding_models.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "chunk_index", name="uq_transcript_chunks_source_index"),
    )
    op.create_index("idx_transcript_chunks_source_id", "transcript_chunks", ["source_id"])
    op.create_index("idx_transcript_chunks_user_id", "transcript_chunks", ["user_id"])
    op.create_index("idx_transcript_chunks_space_id", "transcript_chunks", ["space_id"])


def downgrade() -> None:
    op.drop_table("transcript_chunks")
    op.drop_table("transcript_segments")
    op.drop_table("ingestion_jobs")
    op.drop_table("source_spaces")
    op.drop_table("embedding_models")
