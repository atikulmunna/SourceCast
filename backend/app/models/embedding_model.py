import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EmbeddingModel(Base):
    """
    Registry of embedding models used to produce vector embeddings.
    Each model maps to a dedicated Qdrant collection. Only one model
    should be active at a time; migration jobs handle rotation.
    """

    __tablename__ = "embedding_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Human-readable model identifier, e.g. "all-MiniLM-L6-v2"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Provider identifier, e.g. "sentence-transformers", "openai"
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    # Vector dimensionality, e.g. 384, 768, 1536
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    # Qdrant distance metric: Cosine | Dot | Euclid
    distance_metric: Mapped[str] = mapped_column(String(40), nullable=False, default="Cosine")
    # Qdrant collection name, e.g. "source_chunks_v1_minilm_384"
    qdrant_collection: Mapped[str] = mapped_column(String(160), nullable=False)
    # Only one model should be active at any time
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (UniqueConstraint("name", "dimensions", name="uq_embedding_models_name_dims"),)

    def __repr__(self) -> str:
        return f"<EmbeddingModel name={self.name!r} dims={self.dimensions} active={self.is_active}>"
