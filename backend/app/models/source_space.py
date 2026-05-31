import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceSpace(Base):
    """
    Join table linking a Source to a KnowledgeSpace.
    A source may belong to multiple spaces; user_id is denormalized here
    for faster ownership checks without extra joins.
    """

    __tablename__ = "source_spaces"

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_spaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    # Denormalized for ownership checks
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index("idx_source_spaces_space_id", "space_id"),
        Index("idx_source_spaces_user_id", "user_id"),
    )

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="source_spaces")
    space: Mapped["KnowledgeSpace"] = relationship("KnowledgeSpace", back_populates="source_spaces")

    def __repr__(self) -> str:
        return f"<SourceSpace source_id={self.source_id} space_id={self.space_id}>"


from app.models.knowledge_space import KnowledgeSpace  # noqa: E402, F401
from app.models.source import Source  # noqa: E402, F401
