"""
SourceCast Arq worker entry point.

Usage:
    # From backend/ directory with venv activated:
    python worker.py
"""

import asyncio
import logging

import arq

from app.worker.arq_settings import WorkerSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

if __name__ == "__main__":
    asyncio.run(arq.run_worker(WorkerSettings))  # type: ignore[arg-type]
