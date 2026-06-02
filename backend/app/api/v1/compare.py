from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import ForbiddenException
from app.models.source import Source
from app.schemas.comparison import ComparisonRequest, ComparisonResponse
from app.services.citation_service import add_navigation_urls
from app.services.comparison_service import ComparisonService, ComparisonSource

router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("", response_model=ComparisonResponse)
async def compare_sources(
    data: ComparisonRequest,
    current_user: CurrentUser,
    db: DBDep,
) -> ComparisonResponse:
    unique_source_ids = list(dict.fromkeys(data.source_ids))
    if len(unique_source_ids) != len(data.source_ids):
        raise ForbiddenException("Select distinct sources for comparison")

    result = await db.execute(
        select(Source).where(
            Source.id.in_(unique_source_ids),
            Source.user_id == current_user.id,
        )
    )
    owned_sources = {source.id: source for source in result.scalars().all()}
    if len(owned_sources) != len(unique_source_ids):
        raise ForbiddenException("One or more sources are not accessible")

    response = await ComparisonService(user_id=current_user.id).compare(
        topic=data.topic,
        sources=[
            ComparisonSource(source_id, owned_sources[source_id].title)
            for source_id in unique_source_ids
        ],
        limit_per_source=data.limit_per_source,
    )
    evidence = [item for source in response.sources for item in source.evidence]
    await add_navigation_urls(db, current_user.id, evidence)
    return response
