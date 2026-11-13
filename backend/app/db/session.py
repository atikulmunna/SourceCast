from collections.abc import AsyncGenerator
import uuid

from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _prepared_statement_name() -> str:
    return f"__sourcecast_{uuid.uuid4().hex}__"


def _uses_transaction_pooler(database_url: str) -> bool:
    """True for PgBouncer in transaction mode, such as Neon's `-pooler` endpoint."""
    normalized = database_url.lower()
    host = (make_url(database_url).host or "").lower()
    return (
        "pgbouncer=true" in normalized
        or "prepared_statement_cache_size=0" in normalized
        or host.split(".", 1)[0].endswith("-pooler")
    )


def build_engine_kwargs(database_url: str, debug: bool) -> dict:
    kwargs: dict = {
        "echo": debug,
        "pool_pre_ping": True,
    }
    if _uses_transaction_pooler(database_url):
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {
            "statement_cache_size": 0,
            "prepared_statement_name_func": _prepared_statement_name,
        }
    else:
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    return kwargs


engine = create_async_engine(
    settings.DATABASE_URL,
    **build_engine_kwargs(settings.DATABASE_URL, settings.DEBUG),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
