from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.schemas.comparison import ComparisonResponse, SourceComparison
from app.schemas.qa import EvidenceHit
from app.services.comparison_prompt_service import build_comparison_messages
from app.services.grounded_answer_service import confidence_label, excerpt
from app.services.llm_provider import AnswerProvider, get_answer_provider
from app.services.retrieval_service import RetrievalService

NO_COMPARISON_EVIDENCE = (
    "I could not find enough support for that comparison in the selected sources. "
    "Try a narrower topic or choose different sources."
)


@dataclass
class ComparisonSource:
    id: uuid.UUID
    title: str | None


class ComparisonService:
    def __init__(
        self,
        user_id: uuid.UUID,
        retrieval: RetrievalService | None = None,
        provider: AnswerProvider | None = None,
    ) -> None:
        self.retrieval = retrieval or RetrievalService(user_id=user_id)
        self.provider = provider or get_answer_provider()

    async def compare(
        self,
        topic: str,
        sources: list[ComparisonSource],
        *,
        limit_per_source: int = 3,
    ) -> ComparisonResponse:
        source_results = []
        for source in sources:
            hits = await self.retrieval.search(
                query_text=topic,
                source_ids=[source.id],
                limit=limit_per_source,
                score_threshold=0.25,
            )
            evidence = [
                EvidenceHit(
                    chunk_id=hit.chunk_id,
                    source_id=hit.source_id,
                    space_id=hit.space_id,
                    source_title=hit.source_title or source.title,
                    start_time_sec=hit.start_time_sec,
                    end_time_sec=hit.end_time_sec,
                    excerpt=excerpt(hit.text),
                    score=round(hit.score, 4),
                    confidence_label=confidence_label(hit.score),
                )
                for hit in hits
            ]
            source_results.append(
                SourceComparison(
                    source_id=source.id,
                    source_title=source.title,
                    evidence=evidence,
                    insufficient_evidence=not evidence,
                )
            )

        insufficient_source_ids = [
            source.source_id for source in source_results if source.insufficient_evidence
        ]
        all_evidence = [item for source in source_results for item in source.evidence]
        if not all_evidence:
            return ComparisonResponse(
                topic=topic,
                answer=NO_COMPARISON_EVIDENCE,
                sources=source_results,
                insufficient_source_ids=insufficient_source_ids,
            )

        answer = await self.provider.generate(
            build_comparison_messages(topic, source_results),
            all_evidence,
        )
        return ComparisonResponse(
            topic=topic,
            answer=answer,
            sources=source_results,
            insufficient_source_ids=insufficient_source_ids,
        )
