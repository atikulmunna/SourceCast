from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, DBDep
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.knowledge_space import KnowledgeSpace
from app.models.source import Source
from app.schemas.qa import AskQuestionRequest, AskQuestionResponse, EvidenceHit
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/qa", tags=["qa"])


def _confidence_label(score: float) -> str:
    if score >= 0.72:
        return "High"
    if score >= 0.52:
        return "Medium"
    return "Low"


def _excerpt(text: str, max_chars: int = 500) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


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

    retrieval = RetrievalService(user_id=current_user.id)
    hits = await retrieval.search(
        query_text=data.question,
        space_id=data.space_id,
        source_ids=data.source_ids,
        limit=data.limit,
        score_threshold=0.25,
    )

    evidence = [
        EvidenceHit(
            chunk_id=hit.chunk_id,
            source_id=hit.source_id,
            space_id=hit.space_id,
            source_title=hit.source_title,
            start_time_sec=hit.start_time_sec,
            end_time_sec=hit.end_time_sec,
            excerpt=_excerpt(hit.text),
            score=round(hit.score, 4),
            confidence_label=_confidence_label(hit.score),
        )
        for hit in hits
    ]

    if not evidence:
        return AskQuestionResponse(
            answer=(
                "I could not find enough support for that in the selected sources. "
                "Try selecting more sources or asking a narrower question."
            ),
            evidence=[],
            insufficient_evidence=True,
        )

    lead = evidence[0]
    source_name = lead.source_title or "the selected source"
    answer = (
        f"I found {len(evidence)} relevant transcript moment"
        f"{'' if len(evidence) == 1 else 's'} for this question. "
        f"The strongest match is from {source_name} around "
        f"{int(lead.start_time_sec)}s-{int(lead.end_time_sec)}s. "
        "Use the evidence cards below as the source-grounded basis for the answer."
    )

    return AskQuestionResponse(answer=answer, evidence=evidence)
