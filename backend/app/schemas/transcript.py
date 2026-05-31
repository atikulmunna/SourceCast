"""Pydantic schemas for transcript segments and viewer responses."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel


class TranscriptSegmentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    segment_index: int
    start_time_sec: Decimal
    end_time_sec: Decimal
    text: str
    speaker_label: str | None
    confidence_score: Decimal | None


class TranscriptPageResponse(BaseModel):
    segments: list[TranscriptSegmentOut]
    total: int
    page: int
    limit: int
    has_more: bool
