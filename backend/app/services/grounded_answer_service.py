from __future__ import annotations

import uuid

from app.schemas.qa import AskQuestionResponse, EvidenceHit
from app.services.llm_provider import AnswerProvider, get_answer_provider
from app.services.prompt_service import build_grounded_answer_messages
from app.services.retrieval_service import RetrievalService

NO_EVIDENCE_ANSWER = (
    "I could not find enough support for that in the selected sources. "
    "Try selecting more sources or asking a narrower question."
)


def confidence_label(score: float) -> str:
    if score >= 0.72:
        return "High"
    if score >= 0.52:
        return "Medium"
    return "Low"


def excerpt(text: str, max_chars: int = 500) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."


class GroundedAnswerService:
    def __init__(
        self,
        user_id: uuid.UUID,
        retrieval: RetrievalService | None = None,
        provider: AnswerProvider | None = None,
    ) -> None:
        self.retrieval = retrieval or RetrievalService(user_id=user_id)
        self.provider = provider or get_answer_provider()

    async def answer(
        self,
        question: str,
        *,
        space_id: uuid.UUID | None = None,
        source_ids: list[uuid.UUID] | None = None,
        limit: int = 5,
    ) -> AskQuestionResponse:
        hits = await self.retrieval.search(
            query_text=question,
            space_id=space_id,
            source_ids=source_ids,
            limit=limit,
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
                excerpt=excerpt(hit.text),
                score=round(hit.score, 4),
                confidence_label=confidence_label(hit.score),
            )
            for hit in hits
        ]
        if not evidence:
            return AskQuestionResponse(
                answer=NO_EVIDENCE_ANSWER,
                evidence=[],
                insufficient_evidence=True,
            )

        messages = build_grounded_answer_messages(question, evidence)
        answer = await self.provider.generate(messages, evidence)
        return AskQuestionResponse(answer=answer, evidence=evidence)

