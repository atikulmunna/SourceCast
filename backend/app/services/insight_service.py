import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.evidence_item import EvidenceItem
from app.models.knowledge_space import KnowledgeSpace
from app.models.saved_insight import SavedInsight
from app.models.source import Source
from app.schemas.insights import SavedInsightCreate, SavedInsightOut


class InsightService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_insights(self, user_id: uuid.UUID, space_id: uuid.UUID):
        await self._get_owned_space(user_id, space_id)
        result = await self.db.execute(
            select(SavedInsight)
            .where(SavedInsight.user_id == user_id, SavedInsight.space_id == space_id)
            .order_by(SavedInsight.created_at.desc())
        )
        return [SavedInsightOut.model_validate(insight) for insight in result.scalars().all()]

    async def create_insight(
        self,
        user_id: uuid.UUID,
        data: SavedInsightCreate,
    ) -> SavedInsightOut:
        await self._get_owned_space(user_id, data.space_id)
        if data.source_id:
            await self._get_owned_source(user_id, data.source_id)
        if data.evidence_item_id:
            evidence = await self._get_owned_evidence(user_id, data.evidence_item_id)
            if evidence.source_id and data.source_id and evidence.source_id != data.source_id:
                raise ForbiddenException("Evidence does not belong to the selected source")

        insight = SavedInsight(user_id=user_id, **data.model_dump())
        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)
        return SavedInsightOut.model_validate(insight)

    async def delete_insight(self, user_id: uuid.UUID, insight_id: uuid.UUID) -> None:
        insight = await self._get_owned_insight(user_id, insight_id)
        await self.db.delete(insight)
        await self.db.commit()

    async def _get_owned_space(self, user_id: uuid.UUID, space_id: uuid.UUID) -> KnowledgeSpace:
        result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id == space_id))
        space = result.scalar_one_or_none()
        if not space:
            raise NotFoundException("Knowledge space not found")
        if space.user_id != user_id:
            raise ForbiddenException("You do not own this space")
        return space

    async def _get_owned_source(self, user_id: uuid.UUID, source_id: uuid.UUID) -> Source:
        result = await self.db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if not source:
            raise NotFoundException("Source not found")
        if source.user_id != user_id:
            raise ForbiddenException("You do not own this source")
        return source

    async def _get_owned_evidence(
        self,
        user_id: uuid.UUID,
        evidence_item_id: uuid.UUID,
    ) -> EvidenceItem:
        result = await self.db.execute(select(EvidenceItem).where(EvidenceItem.id == evidence_item_id))
        evidence = result.scalar_one_or_none()
        if not evidence:
            raise NotFoundException("Evidence item not found")
        if evidence.user_id != user_id:
            raise ForbiddenException("You do not own this evidence item")
        return evidence

    async def _get_owned_insight(self, user_id: uuid.UUID, insight_id: uuid.UUID) -> SavedInsight:
        result = await self.db.execute(select(SavedInsight).where(SavedInsight.id == insight_id))
        insight = result.scalar_one_or_none()
        if not insight:
            raise NotFoundException("Saved insight not found")
        if insight.user_id != user_id:
            raise ForbiddenException("You do not own this saved insight")
        return insight
