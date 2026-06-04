FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /usr/sbin/nologin sourcecast

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini worker.py start-web.sh start-worker.sh ./

RUN pip install . \
    && mkdir -p /app/tmp \
    && sed -i 's/\r$//' /app/start-web.sh /app/start-worker.sh \
    && chmod +x /app/start-web.sh /app/start-worker.sh \
    && chown -R sourcecast:sourcecast /app /home/sourcecast

USER sourcecast

EXPOSE 8000

CMD ["./start-web.sh"]
