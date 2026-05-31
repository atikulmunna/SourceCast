import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TranscriptSegment(Base):
    """
    A single raw segment from the Whisper transcription output.
    Segments are the source of truth for the transcript viewer and
    are merged into TranscriptChunks for embedding.

    segment_index is 0-based and unique per source, enabling stable
    pagination and range queries.
    """

    __tablename__ = "transcript_segments"

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

    # Position within the source transcript (0-based)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Whisper timestamps in seconds with millisecond precision
    start_time_sec: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    end_time_sec: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional: populated when speaker diarization is run (P2 feature)
    speaker_label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Whisper per-segment confidence, 0.0–1.0
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        UniqueConstraint("source_id", "segment_index", name="uq_transcript_segments_source_index"),
        # Supports efficient timestamp-range queries for the transcript viewer
        Index(
            "idx_transcript_segments_source_time",
            "source_id",
            "start_time_sec",
        ),
    )

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="transcript_segments")

    def __repr__(self) -> str:
        return (
            f"<TranscriptSegment source_id={self.source_id}"
            f" idx={self.segment_index} [{self.start_time_sec}–{self.end_time_sec}]>"
        )


from app.models.source import Source  # noqa: E402, F401
