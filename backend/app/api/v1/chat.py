import json
import uuid

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, DBDep
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionOut,
    ChatTurnRequest,
)
from app.services.chat_service import ChatService
from app.services.streamed_chat_service import StreamedChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(current_user: CurrentUser, db: DBDep, space_id: uuid.UUID | None = None):
    return await ChatService(db).list_sessions(current_user.id, space_id)


@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(data: ChatSessionCreate, current_user: CurrentUser, db: DBDep):
    return await ChatService(db).create_session(current_user.id, data)


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
async def get_session(session_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    return await ChatService(db).get_session(current_user.id, session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: uuid.UUID, current_user: CurrentUser, db: DBDep) -> None:
    await ChatService(db).delete_session(current_user.id, session_id)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(session_id: uuid.UUID, current_user: CurrentUser, db: DBDep):
    return await ChatService(db).list_messages(current_user.id, session_id)


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    session_id: uuid.UUID,
    data: ChatMessageCreate,
    current_user: CurrentUser,
    db: DBDep,
):
    return await ChatService(db).add_message(current_user.id, session_id, data)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/sessions/{session_id}/ask")
async def ask_session(
    session_id: uuid.UUID,
    data: ChatTurnRequest,
    current_user: CurrentUser,
    db: DBDep,
) -> StreamingResponse:
    async def event_generator():
        yield _sse("chat.started", {"event": "chat.started", "session_id": str(session_id)})
        turn = await StreamedChatService(db).answer(current_user.id, session_id, data)
        yield _sse(
            "chat.delta",
            {
                "event": "chat.delta",
                "session_id": str(session_id),
                "content": turn.assistant_message.content,
            },
        )
        yield _sse(
            "chat.completed",
            {
                "event": "chat.completed",
                "session_id": str(session_id),
                "user_message": turn.user_message.model_dump(mode="json"),
                "assistant_message": turn.assistant_message.model_dump(mode="json"),
                "insufficient_evidence": turn.insufficient_evidence,
            },
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
