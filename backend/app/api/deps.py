import uuid
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CredentialsException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import AuthService

# ── Typed dependency aliases ───────────────────────────────────────────────────
DBDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    db: DBDep,
) -> User:
    """
    Extract and validate the JWT Bearer token from the Authorization header.
    Returns the authenticated User ORM object.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise CredentialsException("Missing or invalid Authorization header")

    token = auth_header.split(" ", 1)[1]
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if not user_id_str:
            raise CredentialsException()
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise CredentialsException()

    service = AuthService(db)
    return await service.get_user_by_id(user_id)


CurrentUser = Annotated[User, Depends(get_current_user)]
