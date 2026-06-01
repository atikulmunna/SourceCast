from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.schemas.qa import AskQuestionRequest, AskQuestionResponse
from app.services.grounded_answer_service import GroundedAnswerService

router = APIRouter(prefix="/qa", tags=["qa"])


async def _assert_space_owner(db: DBDep, user_id: uuid.UUID, space_id: uuid.UUID) -> None:
    result = await db.execute(
        select(KnowledgeSpace).where(
            KnowledgeSpace.id == space_id,
            KnowledgeSpace.user_id == user_id,
        )
    )
    if result.scalar_one_or_none() is None:
        raise NotFoundException("Knowledge space not found")


async def _assert_source_owners(
    db: DBDep,
    user_id: uuid.UUID,
    source_ids: list[uuid.UUID],
) -> None:
    result = await db.execute(
        select(Source.id).where(Source.id.in_(source_ids), Source.user_id == user_id)
    )
    owned_ids = set(result.scalars().all())
    if len(owned_ids) != len(set(source_ids)):
        raise ForbiddenException("One or more sources are not accessible")


@router.post("/ask", response_model=AskQuestionResponse)
async def ask_question(
    data: AskQuestionRequest,
    current_user: CurrentUser,
    db: DBDep,
) -> AskQuestionResponse:
    """Return a first evidence-grounded answer from indexed transcript chunks."""
    if data.space_id:
        await _assert_space_owner(db, current_user.id, data.space_id)
    if data.source_ids:
        await _assert_source_owners(db, current_user.id, data.source_ids)

    return await GroundedAnswerService(user_id=current_user.id).answer(
        question=data.question,
        space_id=data.space_id,
        source_ids=data.source_ids,
        limit=data.limit,
    )
