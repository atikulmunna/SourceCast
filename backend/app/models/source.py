import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Source type: youtube | podcast | audio | rss_episode
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    creator_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    publish_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")

    # Status
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING")
    transcript_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="NOT_STARTED"
    )
    indexing_status: Mapped[str] = mapped_column(String(40), nullable=False, default="NOT_STARTED")

    # Audio storage
    audio_file_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_storage_policy: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DELETE_AFTER_TRANSCRIPTION"
    )
    audio_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        UniqueConstraint("user_id", "canonical_url", name="uq_sources_user_canonical_url"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sources")
    source_spaces: Mapped[list["SourceSpace"]] = relationship(
        "SourceSpace", back_populates="source", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob", back_populates="source", cascade="all, delete-orphan"
    )
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="source", cascade="all, delete-orphan"
    )
    transcript_chunks: Mapped[list["TranscriptChunk"]] = relationship(
        "TranscriptChunk", back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} title={self.title!r} status={self.status}>"


from app.models.ingestion_job import IngestionJob  # noqa: E402, F401
from app.models.source_space import SourceSpace  # noqa: E402, F401
from app.models.transcript_chunk import TranscriptChunk  # noqa: E402, F401
from app.models.transcript_segment import TranscriptSegment  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
