from fastapi import APIRouter, Cookie, Request, Response, status

from app.api.deps import CurrentUser, DBDep
from app.core.config import settings
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "sourcecast_refresh"
COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRES_DAYS * 86400,
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=COOKIE_PATH)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: DBDep) -> UserOut:
    """Register a new user account."""
    service = AuthService(db)
    return await service.register(data)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: DBDep,
) -> TokenResponse:
    """Login and receive an access token. Refresh token is set as HttpOnly cookie."""
    service = AuthService(db)
    access_token, raw_refresh = await service.login(data.email, data.password, request)
    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(
        access_token=access_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: DBDep,
    sourcecast_refresh: str | None = Cookie(default=None),
) -> TokenResponse:
    """
    Rotate refresh token and issue a new access token.
    Refresh token is read from the HttpOnly cookie.
    """
    from app.core.exceptions import CredentialsException

    if not sourcecast_refresh:
        raise CredentialsException("No refresh token cookie found")

    service = AuthService(db)
    new_access, new_refresh = await service.refresh(sourcecast_refresh, request)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(
        access_token=new_access,
        expires_in=settings.ACCESS_TOKEN_EXPIRES_MINUTES * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: DBDep,
    sourcecast_refresh: str | None = Cookie(default=None),
) -> None:
    """Revoke the current refresh token and clear the cookie."""
    if sourcecast_refresh:
        service = AuthService(db)
        await service.logout(sourcecast_refresh)
    _clear_refresh_cookie(response)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    current_user: CurrentUser,
    response: Response,
    db: DBDep,
) -> None:
    """Revoke all refresh tokens for the current user (logout from all devices)."""
    service = AuthService(db)
    await service.logout_all(current_user.id)
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser) -> UserOut:
    """Return the currently authenticated user's profile."""
    return UserOut.model_validate(current_user)
