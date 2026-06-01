from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.schemas.chat import ChatMessageCreate, ChatMessageOut, ChatTurnRequest, EvidenceCreate
from app.services.chat_service import ChatService
from app.services.grounded_answer_service import GroundedAnswerService


@dataclass
class CompletedChatTurn:
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    insufficient_evidence: bool


class StreamedChatService:
    def __init__(self, db, answer_service_factory=GroundedAnswerService):
        self.chat = ChatService(db)
        self.answer_service_factory = answer_service_factory

    async def answer(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        data: ChatTurnRequest,
    ) -> CompletedChatTurn:
        session = await self.chat.get_session(user_id, session_id)
        user_message = await self.chat.add_message(
            user_id,
            session_id,
            ChatMessageCreate(role="user", content=data.question),
        )
        response = await self.answer_service_factory(user_id=user_id).answer(
            data.question,
            space_id=session.space_id,
            source_ids=data.source_ids,
            limit=data.limit,
        )
        evidence = [
            EvidenceCreate(
                source_id=item.source_id,
                chunk_id=item.chunk_id,
                excerpt=item.excerpt,
                source_title=item.source_title,
                start_time_sec=item.start_time_sec,
                end_time_sec=item.end_time_sec,
                relevance_score=item.score,
                confidence_label=item.confidence_label,
            )
            for item in response.evidence
        ]
        assistant_message = await self.chat.add_message(
            user_id,
            session_id,
            ChatMessageCreate(role="assistant", content=response.answer, evidence=evidence),
        )
        return CompletedChatTurn(
            user_message=user_message,
            assistant_message=assistant_message,
            insufficient_evidence=response.insufficient_evidence,
        )
