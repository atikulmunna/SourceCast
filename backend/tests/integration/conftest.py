"""Shared setup for integration tests.

Integration tests write to and delete from real Postgres, Redis and Qdrant. They
must only ever touch the local Docker services from docker-compose.yml, never the
managed services that backend/.env may point at.
"""

from urllib.parse import urlparse

import pytest

from app.core.config import settings
from app.db.session import engine

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@pytest.fixture(scope="session", autouse=True)
def _require_local_services() -> None:
    urls = {
        "DATABASE_URL": settings.DATABASE_URL,
        "DIRECT_URL": settings.DIRECT_URL,
        "REDIS_URL": settings.REDIS_URL,
        "QDRANT_URL": settings.QDRANT_URL,
    }
    remote = {
        name: urlparse(url).hostname
        for name, url in urls.items()
        if url and urlparse(url).hostname not in LOCAL_HOSTS
    }
    if remote:
        details = ", ".join(f"{name} -> {host}" for name, host in remote.items())
        pytest.exit(
            "Integration tests only run against local services. Refusing non-local "
            f"targets: {details}. Run them with check_integration.ps1.",
            returncode=1,
        )


@pytest.fixture(autouse=True)
async def _dispose_engine_after_test():
    """Drop pooled connections so the next test's event loop starts clean."""
    yield
    await engine.dispose()
