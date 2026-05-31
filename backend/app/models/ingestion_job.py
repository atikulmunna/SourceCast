import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Valid status values per SRS §15.1
JOB_STATUSES = (
    "PENDING",
    "QUEUED",
    "DOWNLOADING",
    "TRANSCRIBING",
    "SEGMENTING",
    "CHUNKING",
    "EMBEDDING",
    "INDEXING",
    "CLEANING_UP",
    "COMPLETED",
    "FAILED",
    "STALE",
    "CANCELLED",
)


class IngestionJob(Base):
    """
    Tracks the full lifecycle of a source ingestion job.
    Workers update this row at each stage transition and on heartbeat.
    The SSE endpoint polls/watches this row to stream progress to the client.
    """

    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # ── Job metadata ────────────────────────────────────────────────────────
    job_type: Mapped[str] = mapped_column(String(60), nullable=False, default="SOURCE_INGESTION")
    # Arq / Celery task ID for direct worker lookup
    worker_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── Lifecycle ────────────────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="PENDING", index=True)
    # Current named stage, e.g. "transcription", "embedding"
    stage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # 0–100
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Human-readable message for the UI progress component
    current_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_seconds_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Reliability ──────────────────────────────────────────────────────────
    # Workers update this timestamp regularly; used for stale detection
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Structured log entries: [{"ts": "...", "level": "info", "msg": "..."}]
    logs: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")

    # ── Timestamps ───────────────────────────────────────────────────────────
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    # ── Relationships ────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="ingestion_jobs")
    source: Mapped["Source"] = relationship("Source", back_populates="ingestion_jobs")

    @property
    def is_terminal(self) -> bool:
        return self.status in ("COMPLETED", "FAILED", "STALE", "CANCELLED")

    @property
    def is_retryable(self) -> bool:
        return self.status in ("FAILED", "STALE") and self.retry_count < self.max_retries

    def __repr__(self) -> str:
        return f"<IngestionJob id={self.id} status={self.status} progress={self.progress}%>"


from app.models.source import Source  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
