import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChatSessionCreate(BaseModel):
    space_id: uuid.UUID
    title: str = Field(default="New research chat", min_length=1, max_length=255)


class ChatSessionOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    space_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class EvidenceCreate(BaseModel):
    source_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    claim_text: str | None = None
    excerpt: str = Field(min_length=1, max_length=500)
    source_title: str | None = Field(default=None, max_length=500)
    start_time_sec: Decimal = Field(ge=0)
    end_time_sec: Decimal = Field(ge=0)
    relevance_score: Decimal | None = Field(default=None, ge=0, le=1)
    confidence_label: Literal["High", "Medium", "Low", "Insufficient"]

    @model_validator(mode="after")
    def validate_timestamp_range(self):
        if self.end_time_sec < self.start_time_sec:
            raise ValueError("Evidence end timestamp must be after its start timestamp")
        return self


class EvidenceOut(EvidenceCreate):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    message_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    navigation_url: str | None = None


class ChatMessageCreate(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1, max_length=50000)
    evidence: list[EvidenceCreate] = Field(default_factory=list)


class ChatTurnRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    source_ids: list[uuid.UUID] | None = None
    limit: int = Field(default=5, ge=1, le=12)


class ChatMessageOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    content: str
    sequence_number: int
    created_at: datetime
    evidence: list[EvidenceOut] = Field(default_factory=list)
