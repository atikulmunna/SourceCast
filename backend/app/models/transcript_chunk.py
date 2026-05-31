import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TranscriptChunk(Base):
    """
    A merged window of TranscriptSegments sized for embedding.
    Each chunk maps 1:1 to a Qdrant vector point once embedded.

    chunk_index is 0-based and unique per source. vector_point_id
    is null until the embedding stage of the ingestion job completes.
    """

    __tablename__ = "transcript_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Nullable: chunk belongs to the source; space association is for scoped retrieval
    space_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_spaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Position within the source (0-based)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamp span covered by this chunk
    start_time_sec: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    end_time_sec: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Approximate token count used during chunking to stay within model limits
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Vector metadata ──────────────────────────────────────────────────────
    # FK to embedding_models; null until embedding stage runs
    embedding_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("embedding_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Qdrant collection this chunk's vector lives in
    vector_collection: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    # Qdrant point ID — null until embedding stage completes
    vector_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_transcript_chunks_source_index"),
    )

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="transcript_chunks")
    embedding_model: Mapped["EmbeddingModel"] = relationship("EmbeddingModel")

    def __repr__(self) -> str:
        return (
            f"<TranscriptChunk source_id={self.source_id}"
            f" idx={self.chunk_index} [{self.start_time_sec}–{self.end_time_sec}]>"
        )


from app.models.embedding_model import EmbeddingModel  # noqa: E402, F401
from app.models.source import Source  # noqa: E402, F401
