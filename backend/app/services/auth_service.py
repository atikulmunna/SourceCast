from datetime import datetime, timezone
import uuid

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictException,
    CredentialsException,
    ForbiddenException,
    NotFoundException,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
    verify_refresh_token,
    settings,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest, TokenResponse, UserOut


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest) -> UserOut:
        # Check duplicate email
        result = await self.db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise ConflictException("Email already registered")

        user = User(
            email=data.email,
            name=data.name,
            password_hash=hash_password(data.password),
            role="USER",
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return UserOut.model_validate(user)

    async def login(
        self, email: str, password: str, request: Request | None = None
    ) -> tuple[str, str]:
        """
        Returns (access_token, raw_refresh_token).
        Caller is responsible for setting the cookie.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise CredentialsException("Invalid email or password")
        if not user.is_active:
            raise ForbiddenException("Account is disabled")

        access_token = create_access_token(str(user.id))
        raw_refresh = generate_refresh_token()

        rt = RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_token_expiry(),
            user_agent=request.headers.get("user-agent") if request else None,
            ip_address=str(request.client.host) if request and request.client else None,
        )
        self.db.add(rt)
        await self.db.commit()

        return access_token, raw_refresh

    async def refresh(self, raw_token: str, request: Request | None = None) -> tuple[str, str]:
        """
        Validate refresh token, rotate it, return (new_access_token, new_raw_refresh_token).
        """
        # Find all non-expired, non-revoked tokens and check against hash
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        tokens = result.scalars().all()

        matched: RefreshToken | None = None
        for token in tokens:
            if verify_refresh_token(raw_token, token.token_hash):
                matched = token
                break

        if not matched:
            raise CredentialsException("Invalid or expired refresh token")

        # Get user
        result = await self.db.execute(select(User).where(User.id == matched.user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise CredentialsException("User not found or inactive")

        # Issue new tokens (rotation)
        new_access = create_access_token(str(user.id))
        new_raw_refresh = generate_refresh_token()

        new_rt = RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_refresh_token(new_raw_refresh),
            expires_at=refresh_token_expiry(),
            user_agent=request.headers.get("user-agent") if request else None,
            ip_address=str(request.client.host) if request and request.client else None,
        )
        self.db.add(new_rt)

        # Revoke old token and record rotation chain
        matched.revoked_at = datetime.now(timezone.utc)
        matched.replaced_by_token_id = new_rt.id

        await self.db.commit()
        return new_access, new_raw_refresh

    async def logout(self, raw_token: str) -> None:
        """Revoke a specific refresh token."""
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        )
        tokens = result.scalars().all()
        for token in tokens:
            if verify_refresh_token(raw_token, token.token_hash):
                token.revoked_at = datetime.now(timezone.utc)
                await self.db.commit()
                return

    async def logout_all(self, user_id: uuid.UUID) -> None:
        """Revoke all active refresh tokens for a user."""
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        tokens = result.scalars().all()
        now = datetime.now(timezone.utc)
        for token in tokens:
            token.revoked_at = now
        await self.db.commit()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("User not found")
        return user
