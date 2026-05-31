"""
Pydantic schemas for ingestion jobs and SSE event payloads.
Event shapes match the SRS §15.3–15.6 contracts exactly.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field

# ── Job read schema ────────────────────────────────────────────────────────────


class JobOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    source_id: uuid.UUID | None
    job_type: str
    status: str
    stage: str | None
    progress: int
    current_step: str | None
    estimated_seconds_remaining: int | None
    heartbeat_at: datetime | None
    error_code: str | None
    error_message: str | None
    retry_count: int
    max_retries: int
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def is_retryable(self) -> bool:
        return self.status in ("FAILED", "STALE") and self.retry_count < self.max_retries


# ── SSE event payloads (SRS §15.3–15.6) ───────────────────────────────────────


class JobProgressEvent(BaseModel):
    event: str = "job.progress"
    job_id: str
    source_id: str | None
    status: str
    stage: str | None
    progress: int
    message: str
    current_step: str | None
    estimated_seconds_remaining: int | None
    updated_at: str


class JobCompletedEvent(BaseModel):
    event: str = "job.completed"
    job_id: str
    source_id: str | None
    status: str = "COMPLETED"
    progress: int = 100
    message: str = "Source is ready for research."
    chunk_count: int
    duration_sec: int | None
    audio_deleted: bool
    updated_at: str


class JobFailedEvent(BaseModel):
    event: str = "job.failed"
    job_id: str
    source_id: str | None
    status: str = "FAILED"
    stage: str | None
    error_code: str
    message: str
    retryable: bool
    retry_after_seconds: int = 60
    updated_at: str


class JobHeartbeatEvent(BaseModel):
    event: str = "job.heartbeat"
    job_id: str
    updated_at: str
