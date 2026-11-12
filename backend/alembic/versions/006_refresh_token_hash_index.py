"""Unique index on refresh_tokens.token_hash

Refresh and logout look a token up by its SHA-256 hash instead of loading every
active token. Hashes of random 64-byte tokens never collide, so the unique index
is safe to add on existing data.

Revision ID: 006_refresh_token_hash_index
Revises: 005_research_briefs_schema
Create Date: 2026-11-13
"""

from alembic import op

revision: str = "006_refresh_token_hash_index"
down_revision: str | None = "005_research_briefs_schema"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_index(
        "uq_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_refresh_tokens_token_hash", table_name="refresh_tokens")
