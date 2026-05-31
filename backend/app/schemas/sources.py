import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Ingestion request ─────────────────────────────────────────────────────────


class SourceCreateRequest(BaseModel):
    url: str = Field(min_length=5, max_length=2048)
    space_id: uuid.UUID
    whisper_model: str | None = None
    language: str | None = None
    audio_storage_policy: str = "DELETE_AFTER_TRANSCRIPTION"


# ── Source read schema ─────────────────────────────────────────────────────────


class SourceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    source_type: str
    source_url: str
    canonical_url: str | None
    title: str | None
    creator_name: str | None
    thumbnail_url: str | None
    duration_sec: int | None
    language: str
    status: str
    transcript_status: str
    indexing_status: str
    audio_storage_policy: str
    created_at: datetime
    updated_at: datetime


# ── Ingestion response ─────────────────────────────────────────────────────────


class SourceIngestResponse(BaseModel):
    source: SourceOut
    job_id: uuid.UUID
    job_status: str


# ── Preview request ────────────────────────────────────────────────────────────


class SourcePreviewRequest(BaseModel):
    url: str = Field(min_length=5, max_length=2048)
    whisper_model: str | None = Field(
        default=None,
        description="Whisper model to use for transcription. Affects time estimate.",
    )


class ProcessingEstimate(BaseModel):
    estimated_seconds: int
    estimated_label: str  # e.g. "~12 min"
    model_used: str
    is_long_content: bool
    warning: str | None = None


class SourcePreviewResponse(BaseModel):
    url: str
    canonical_url: str | None
    source_type: str  # youtube | podcast | audio
    title: str | None
    creator_name: str | None
    thumbnail_url: str | None
    duration_sec: int | None
    duration_label: str | None  # e.g. "1h 23m 45s"
    publish_date: datetime | None
    language: str | None
    processing_estimate: ProcessingEstimate | None
    error: str | None = None
