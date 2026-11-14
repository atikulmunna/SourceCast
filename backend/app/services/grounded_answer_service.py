from __future__ import annotations

import uuid

from app.schemas.qa import AskQuestionResponse, EvidenceHit
from app.services.llm_provider import AnswerProvider, get_answer_provider
from app.services.prompt_service import INSUFFICIENT_MARKER, build_grounded_answer_messages
from app.services.retrieval_service import RetrievalService

NO_EVIDENCE_ANSWER = (
    "I could not find enough support for that in the selected sources. "
    "Try selecting more sources or asking a narrower question."
)

# Calibrated on the eval with voyage-4-lite (2026-11-14). Among top-5 results,
# about 75% of chunks scoring 0.60 or more were the expected moment, about half
# of chunks scoring 0.50 to 0.60, and few below 0.50.
HIGH_CONFIDENCE = 0.60
MEDIUM_CONFIDENCE = 0.50
# Evidence below this cosine similarity is not shown to the model. The lowest
# score of a relevant chunk in the eval was 0.30, so nothing relevant is lost.
SCORE_THRESHOLD = 0.28


def confidence_label(score: float) -> str:
    if score >= HIGH_CONFIDENCE:
        return "High"
    if score >= MEDIUM_CONFIDENCE:
        return "Medium"
    return "Low"


def is_insufficient(answer: str) -> bool:
    """True when the model replied with the insufficient-evidence marker."""
    return answer.strip().strip("*`'\".").upper().startswith(INSUFFICIENT_MARKER)


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
            score_threshold=SCORE_THRESHOLD,
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
                text=hit.text,
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
        answer = await self.provider.generate(messages)
        if is_insufficient(answer):
            # Evidence the model judged irrelevant is not shown as support.
            return AskQuestionResponse(
                answer=NO_EVIDENCE_ANSWER, evidence=[], insufficient_evidence=True
            )
        return AskQuestionResponse(answer=answer, evidence=evidence)
