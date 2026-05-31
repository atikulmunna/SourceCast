import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="USER")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    # Relationships
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_spaces: Mapped[list["KnowledgeSpace"]] = relationship(
        "KnowledgeSpace", back_populates="user", cascade="all, delete-orphan"
    )
    sources: Mapped[list["Source"]] = relationship(
        "Source", back_populates="user", cascade="all, delete-orphan"
    )
    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(
        "IngestionJob", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# Circular import avoidance — import models here so relationships resolve
from app.models.ingestion_job import IngestionJob  # noqa: E402, F401
from app.models.knowledge_space import KnowledgeSpace  # noqa: E402, F401
from app.models.refresh_token import RefreshToken  # noqa: E402, F401
from app.models.source import Source  # noqa: E402, F401
