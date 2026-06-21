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
    max_jobs = settings.WORKER_MAX_JOBS

    # Slow idle polling keeps managed Redis free-tier request usage under control.
    poll_delay = settings.WORKER_POLL_DELAY_SECONDS

    # Timeout per job in seconds — 2 hours for long-form content
    job_timeout = 7200

    # How long to keep job results in Redis
    keep_result = 3600  # 1 hour

    # Retry failed jobs up to this many times
    max_tries = 1  # IngestionJob.max_retries handles retry logic in DB

    on_startup = None
    on_shutdown = None
