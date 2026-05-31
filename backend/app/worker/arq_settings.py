"""
Arq worker configuration.

Run the worker with:
    python worker.py

Or directly:
    .venv/Scripts/python.exe worker.py
"""

from arq.connections import RedisSettings

from app.core.config import settings
from app.worker.ingestion_tasks import ingest_source


class WorkerSettings:
    """Arq WorkerSettings class — arq discovers this automatically."""

    functions = [ingest_source]

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    # Maximum number of concurrent jobs
    max_jobs = 4

    # Timeout per job in seconds — 2 hours for long-form content
    job_timeout = 7200

    # How long to keep job results in Redis
    keep_result = 3600  # 1 hour

    # Retry failed jobs up to this many times
    max_tries = 1  # IngestionJob.max_retries handles retry logic in DB

    on_startup = None
    on_shutdown = None
