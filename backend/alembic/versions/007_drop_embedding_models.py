"""Drop the embedding_models table

The embedding model is a setting (EMBEDDING_MODEL, EMBEDDING_DIMENSIONS), and the
Qdrant collection name is derived from it. Each chunk still records the
collection its vector went to in transcript_chunks.vector_collection, which names
the model and dimensions, so the registry table was a second source of truth.

Revision ID: 007_drop_embedding_models
Revises: 006_refresh_token_hash_index
Create Date: 2026-11-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_drop_embedding_models"
down_revision: str | None = "006_refresh_token_hash_index"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Dropping the column also drops its foreign key to embedding_models.
    op.drop_column("transcript_chunks", "embedding_model_id")
    op.drop_table("embedding_models")


def downgrade() -> None:
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
    op.execute(
        """
        INSERT INTO embedding_models (id, name, provider, dimensions, distance_metric,
                                      qdrant_collection, is_active)
        VALUES (gen_random_uuid(), 'all-MiniLM-L6-v2', 'sentence-transformers', 384,
                'Cosine', 'source_chunks_v1_minilm_384', true)
        """
    )
    op.add_column(
        "transcript_chunks",
        sa.Column("embedding_model_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        None,
        "transcript_chunks",
        "embedding_models",
        ["embedding_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
