import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResearchBriefCreate(BaseModel):
    space_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    topic: str | None = Field(default=None, max_length=1000)
    source_ids: list[uuid.UUID] = Field(default_factory=list, max_length=12)


class ResearchBriefOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    space_id: uuid.UUID
    title: str
    topic: str | None
    content_markdown: str | None
    source_ids: list[uuid.UUID]
    status: Literal["READY", "FAILED"]
    created_at: datetime
    updated_at: datetime
