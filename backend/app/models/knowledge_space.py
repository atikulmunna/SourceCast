import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeSpace(Base):
    __tablename__ = "knowledge_spaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_knowledge_spaces_user_name"),)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="knowledge_spaces")
    source_spaces: Mapped[list["SourceSpace"]] = relationship(
        "SourceSpace", back_populates="space", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<KnowledgeSpace id={self.id} name={self.name}>"


from app.models.source_space import SourceSpace  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401
