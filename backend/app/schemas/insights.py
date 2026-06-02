import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SavedInsightCreate(BaseModel):
    space_id: uuid.UUID
    source_id: uuid.UUID | None = None
    evidence_item_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    content: str = Field(min_length=1, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class SavedInsightOut(SavedInsightCreate):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
