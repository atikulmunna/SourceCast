"""Pydantic schemas for ingestion jobs."""

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

