from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, Field


class AskQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    space_id: uuid.UUID | None = None
    source_ids: list[uuid.UUID] | None = None
    limit: int = Field(default=5, ge=1, le=12)


class EvidenceHit(BaseModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    space_id: uuid.UUID | None
    source_title: str | None
    start_time_sec: Decimal
    end_time_sec: Decimal
    excerpt: str
    score: float
    confidence_label: str


class AskQuestionResponse(BaseModel):
    answer: str
    evidence: list[EvidenceHit]
    insufficient_evidence: bool = False

