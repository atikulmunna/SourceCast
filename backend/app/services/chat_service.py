import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException, UnprocessableException
from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.evidence_item import EvidenceItem
from app.models.knowledge_space import KnowledgeSpace
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, ChatSessionCreate, ChatSessionOut


class ChatService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_sessions(self, user_id: uuid.UUID, space_id: uuid.UUID | None = None):
        query = select(ChatSession).where(ChatSession.user_id == user_id)
        if space_id:
            await self._get_owned_space(user_id, space_id)
            query = query.where(ChatSession.space_id == space_id)
        result = await self.db.execute(query.order_by(ChatSession.updated_at.desc()))
        return [ChatSessionOut.model_validate(session) for session in result.scalars().all()]

    async def create_session(self, user_id: uuid.UUID, data: ChatSessionCreate) -> ChatSessionOut:
        await self._get_owned_space(user_id, data.space_id)
        session = ChatSession(user_id=user_id, space_id=data.space_id, title=data.title)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return ChatSessionOut.model_validate(session)

    async def get_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> ChatSessionOut:
        return ChatSessionOut.model_validate(await self._get_owned_session(user_id, session_id))

    async def delete_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        session = await self._get_owned_session(user_id, session_id)
        await self.db.delete(session)
        await self.db.commit()

    async def list_messages(self, user_id: uuid.UUID, session_id: uuid.UUID):
        await self._get_owned_session(user_id, session_id)
        result = await self.db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_number)
        )
        return [await self._message_out(message) for message in result.scalars().all()]

    async def add_message(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        data: ChatMessageCreate,
    ) -> ChatMessageOut:
        session = await self._get_owned_session(user_id, session_id)
        if data.evidence and data.role != "assistant":
            raise UnprocessableException("Evidence can only be attached to assistant messages")

        result = await self.db.execute(
            select(func.coalesce(func.max(ChatMessage.sequence_number), 0)).where(
                ChatMessage.session_id == session_id
            )
        )
        next_sequence = result.scalar_one() + 1
        message = ChatMessage(
            session_id=session_id,
            user_id=user_id,
            role=data.role,
            content=data.content,
            sequence_number=next_sequence,
        )
        self.db.add(message)
        await self.db.flush()

        for evidence in data.evidence:
            self.db.add(
                EvidenceItem(
                    message_id=message.id,
                    user_id=user_id,
                    **evidence.model_dump(),
                )
            )

        session.updated_at = message.created_at
        await self.db.commit()
        await self.db.refresh(message)
        return await self._message_out(message)

    async def _message_out(self, message: ChatMessage) -> ChatMessageOut:
        result = await self.db.execute(
            select(EvidenceItem)
            .where(EvidenceItem.message_id == message.id)
            .order_by(EvidenceItem.created_at)
        )
        evidence = result.scalars().all()
        return ChatMessageOut(
            id=message.id,
            session_id=message.session_id,
            user_id=message.user_id,
            role=message.role,
            content=message.content,
            sequence_number=message.sequence_number,
            created_at=message.created_at,
            evidence=evidence,
        )

    async def _get_owned_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> ChatSession:
        result = await self.db.execute(select(ChatSession).where(ChatSession.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise NotFoundException("Chat session not found")
        if session.user_id != user_id:
            raise ForbiddenException("You do not own this chat session")
        return session

    async def _get_owned_space(self, user_id: uuid.UUID, space_id: uuid.UUID) -> KnowledgeSpace:
        result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id == space_id))
        space = result.scalar_one_or_none()
        if not space:
            raise NotFoundException("Knowledge space not found")
        if space.user_id != user_id:
            raise ForbiddenException("You do not own this space")
        return space

