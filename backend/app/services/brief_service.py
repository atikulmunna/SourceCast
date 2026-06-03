import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.knowledge_space import KnowledgeSpace
from app.models.research_brief import ResearchBrief
from app.models.saved_insight import SavedInsight
from app.models.source import Source
from app.models.source_space import SourceSpace
from app.schemas.briefs import ResearchBriefCreate, ResearchBriefOut
from app.schemas.insights import SavedInsightOut
from app.services.brief_markdown_service import BriefSource, build_research_brief_markdown


class BriefService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_briefs(self, user_id: uuid.UUID, space_id: uuid.UUID):
        await self._get_owned_space(user_id, space_id)
        result = await self.db.execute(
            select(ResearchBrief)
            .where(ResearchBrief.user_id == user_id, ResearchBrief.space_id == space_id)
            .order_by(ResearchBrief.created_at.desc())
        )
        return [ResearchBriefOut.model_validate(brief) for brief in result.scalars().all()]

    async def create_brief(self, user_id: uuid.UUID, data: ResearchBriefCreate) -> ResearchBriefOut:
        await self._get_owned_space(user_id, data.space_id)
        sources = await self._get_owned_sources_in_space(user_id, data.space_id, data.source_ids)
        insights = await self._get_space_insights(user_id, data.space_id)
        markdown = build_research_brief_markdown(
            data.title,
            data.topic,
            [
                BriefSource(
                    title=source.title or "Untitled source",
                    source_type=source.source_type,
                    canonical_url=source.canonical_url,
                    source_url=source.source_url,
                )
                for source in sources
            ],
            [SavedInsightOut.model_validate(insight) for insight in insights],
        )
        brief = ResearchBrief(
            user_id=user_id,
            space_id=data.space_id,
            title=data.title,
            topic=data.topic,
            content_markdown=markdown,
            source_ids=[source.id for source in sources],
            status="READY",
        )
        self.db.add(brief)
        await self.db.commit()
        await self.db.refresh(brief)
        return ResearchBriefOut.model_validate(brief)

    async def get_brief(self, user_id: uuid.UUID, brief_id: uuid.UUID) -> ResearchBriefOut:
        return ResearchBriefOut.model_validate(await self._get_owned_brief(user_id, brief_id))

    async def export_markdown(self, user_id: uuid.UUID, brief_id: uuid.UUID) -> tuple[str, str]:
        brief = await self._get_owned_brief(user_id, brief_id)
        filename = slugify_filename(brief.title) + ".md"
        return filename, brief.content_markdown or ""

    async def delete_brief(self, user_id: uuid.UUID, brief_id: uuid.UUID) -> None:
        brief = await self._get_owned_brief(user_id, brief_id)
        await self.db.delete(brief)
        await self.db.commit()

    async def _get_owned_space(self, user_id: uuid.UUID, space_id: uuid.UUID) -> KnowledgeSpace:
        result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id == space_id))
        space = result.scalar_one_or_none()
        if not space:
            raise NotFoundException("Knowledge space not found")
        if space.user_id != user_id:
            raise ForbiddenException("You do not own this space")
        return space

    async def _get_owned_sources_in_space(
        self,
        user_id: uuid.UUID,
        space_id: uuid.UUID,
        source_ids: list[uuid.UUID],
    ) -> list[Source]:
        if not source_ids:
            result = await self.db.execute(
                select(Source)
                .join(SourceSpace, SourceSpace.source_id == Source.id)
                .where(Source.user_id == user_id, SourceSpace.space_id == space_id)
            )
            return list(result.scalars().all())

        unique_source_ids = list(dict.fromkeys(source_ids))
        if len(unique_source_ids) != len(source_ids):
            raise ForbiddenException("Select distinct sources for a brief")
        result = await self.db.execute(
            select(Source)
            .join(SourceSpace, SourceSpace.source_id == Source.id)
            .where(
                Source.id.in_(unique_source_ids),
                Source.user_id == user_id,
                SourceSpace.space_id == space_id,
            )
        )
        sources = {source.id: source for source in result.scalars().all()}
        if len(sources) != len(unique_source_ids):
            raise ForbiddenException("One or more sources are not accessible in this space")
        return [sources[source_id] for source_id in unique_source_ids]

    async def _get_space_insights(self, user_id: uuid.UUID, space_id: uuid.UUID) -> list[SavedInsight]:
        result = await self.db.execute(
            select(SavedInsight)
            .where(SavedInsight.user_id == user_id, SavedInsight.space_id == space_id)
            .order_by(SavedInsight.created_at.desc())
        )
        return list(result.scalars().all())

    async def _get_owned_brief(self, user_id: uuid.UUID, brief_id: uuid.UUID) -> ResearchBrief:
        result = await self.db.execute(select(ResearchBrief).where(ResearchBrief.id == brief_id))
        brief = result.scalar_one_or_none()
        if not brief:
            raise NotFoundException("Research brief not found")
        if brief.user_id != user_id:
            raise ForbiddenException("You do not own this research brief")
        return brief


def slugify_filename(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "research-brief"
