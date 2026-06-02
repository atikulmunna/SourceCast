from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.qa import EvidenceHit


class ComparisonRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=1000)
    source_ids: list[uuid.UUID] = Field(min_length=2, max_length=8)
    limit_per_source: int = Field(default=3, ge=1, le=6)


class SourceComparison(BaseModel):
    source_id: uuid.UUID
    source_title: str | None
    evidence: list[EvidenceHit]
    insufficient_evidence: bool = False


class ComparisonResponse(BaseModel):
    topic: str
    answer: str
    sources: list[SourceComparison]
    insufficient_source_ids: list[uuid.UUID] = Field(default_factory=list)
