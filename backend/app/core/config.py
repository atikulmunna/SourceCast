from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from sqlalchemy.engine import make_url
from typing import Literal

PLACEHOLDER_SECRET_MARKERS = ("change-me", "in-production", "replace-with", "your-", "your_")


def normalize_database_url(url: str) -> str:
    """Accept a database URL as Neon (or any libpq tool) prints it.

    asyncpg takes `ssl` where libpq takes `sslmode`, and has no `channel_binding`
    option, so a pasted `postgresql://...?sslmode=require&channel_binding=require`
    would otherwise fail on the first connection. URLs already in asyncpg form are
    returned unchanged.
    """
    if not url:
        return url
    parsed = make_url(url)
    query = dict(parsed.query)
    if "sslmode" in query:
        query.setdefault("ssl", query.pop("sslmode"))
    query.pop("channel_binding", None)
    drivername = parsed.drivername
    if drivername in ("postgres", "postgresql"):
        drivername = "postgresql+asyncpg"
    if drivername == parsed.drivername and query == dict(parsed.query):
        return url
    return parsed.set(drivername=drivername, query=query).render_as_string(hide_password=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    DEBUG: bool = True
    PUBLIC_SIGNUP_ENABLED: bool = True

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.ENVIRONMENT != "production":
            return self

        if self.DEBUG:
            raise ValueError("DEBUG must be false when ENVIRONMENT=production")

        for name in ("JWT_ACCESS_SECRET", "JWT_REFRESH_SECRET"):
            value = getattr(self, name)
            normalized = value.lower()
            if len(value) < 32 or any(marker in normalized for marker in PLACEHOLDER_SECRET_MARKERS):
                raise ValueError(f"{name} must be a strong non-placeholder secret in production")

        redis_url = self.REDIS_URL.lower()
        if "upstash.io" in redis_url and redis_url.startswith("redis://"):
            raise ValueError("Upstash Redis requires a rediss:// TLS URL in production")

        key = self.OPENROUTER_API_KEY.lower()
        if not key or any(marker in key for marker in PLACEHOLDER_SECRET_MARKERS):
            raise ValueError("OPENROUTER_API_KEY must be set in production")

        return self

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://sourcecast:sourcecast_dev@localhost:5432/sourcecast"
    )
    DIRECT_URL: str = ""

    @field_validator("DATABASE_URL", "DIRECT_URL")
    @classmethod
    def normalize_database_urls(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def migration_database_url(self) -> str:
        return self.DIRECT_URL or self.DATABASE_URL

    # ── Auth ──────────────────────────────────────────────────────────────────
    JWT_ACCESS_SECRET: str = "change-me-access-secret"
    JWT_REFRESH_SECRET: str = "change-me-refresh-secret"
    ACCESS_TOKEN_EXPIRES_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRES_DAYS: int = 14

    # ── Infrastructure ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    JOB_STALE_TIMEOUT_SECONDS: int = 120
    WORKER_MAX_JOBS: int = 1
    WORKER_POLL_DELAY_SECONDS: float = 10.0

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_PROVIDER: Literal["local", "s3"] = "local"
    AUDIO_STORAGE_POLICY: Literal[
        "DELETE_AFTER_TRANSCRIPTION", "RETAIN"
    ] = "DELETE_AFTER_TRANSCRIPTION"

    # ── OpenRouter ────────────────────────────────────────────────────────────
    # The only AI provider: chat answers, transcription and embeddings. Server
    # side only; never expose the key to the frontend.
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_TIMEOUT_SECONDS: float = 60.0
    OPENROUTER_MAX_RETRIES: int = 3
    # Chat uses the Auto Router; it picks a model per request within these limits.
    # Defaults chosen with the eval (2026-11-13): on full-chunk prompts these two
    # models cite correctly on 96% of answerable questions and refuse all
    # unanswerable ones, at about $0.0003 per answer. `medium` scored the same at
    # about 6x the cost; claude-haiku-5.5 hedged too often (72%).
    CHAT_MODEL: str = "openrouter/auto"
    CHAT_ALLOWED_MODELS: str = "openai/gpt-6-luna,deepseek/deepseek-v4.1-flash*"
    CHAT_COST_TIER: Literal["low", "medium", "high"] = "low"
    CHAT_MAX_PROMPT_PRICE: float = 0.5  # USD per million tokens; 0 means no cap
    CHAT_MAX_COMPLETION_PRICE: float = 2.0  # USD per million tokens; 0 means no cap
    # Fixed models: every vector in an index must come from the same model.
    # voyage-4-lite found the expected moment in the top 5 for every eval question
    # (text-embedding-3-small: 96%) at the same price, with the smallest vectors of
    # the models tested (2026-11-14). Changing either value starts a new collection.
    EMBEDDING_MODEL: str = "mongodb/voyage-4-lite"
    EMBEDDING_DIMENSIONS: int = 1024
    # whisper-large-v3-turbo matched whisper-large-v3 on a one-hour talk (timestamps
    # within 1.6 s of the captions at start, middle and end) at $0.012 per hour of
    # audio against $0.027, and ran faster (2026-11-14).
    TRANSCRIPTION_MODEL: str = "openai/whisper-large-v3-turbo"
    # Audio is split into chunks this long so each upload stays under OpenRouter's
    # 25 MB cap and 60 second upstream timeout (16 kHz mono, 32 kbit/s: ~2.4 MB).
    TRANSCRIPTION_CHUNK_MINUTES: int = 10
    # Per chunk. OpenRouter's upstream gives up after 60 seconds.
    TRANSCRIPTION_TIMEOUT_SECONDS: int = 120

    @property
    def chat_allowed_models(self) -> list[str]:
        return [item.strip() for item in self.CHAT_ALLOWED_MODELS.split(",") if item.strip()]

    # ── AI / RAG ──────────────────────────────────────────────────────────────
    WHISPER_MODEL: str = "tiny"
    YTDLP_COOKIES_FILE: str = ""
    YTDLP_PROXY_URL: str = ""
    YOUTUBE_TRANSCRIPT_LANGUAGES: str = "en,en-US,en-GB"
    YOUTUBE_TRANSCRIPT_PROXY_HTTP_URL: str = ""
    YOUTUBE_TRANSCRIPT_PROXY_HTTPS_URL: str = ""
    WEBSHARE_PROXY_USERNAME: str = ""
    WEBSHARE_PROXY_PASSWORD: str = ""
    WEBSHARE_PROXY_LOCATIONS: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [self.FRONTEND_URL]

    # ── Processing time estimation ─────────────────────────────────────────────
    # Approximate real-time factor per Whisper model on CPU.
    # A factor of 8 means 1 second of audio takes ~8 seconds to transcribe.
    WHISPER_RTF_FACTORS: dict[str, float] = {
        "tiny": 3.0,
        "base": 6.0,
        "small": 10.0,
        "medium": 20.0,
        "large": 40.0,
        "large-v2": 40.0,
        "large-v3": 45.0,
    }

    def estimate_transcription_seconds(
        self, duration_sec: int, model: str | None = None
    ) -> int:
        """Return estimated transcription wall-clock seconds for the given audio duration."""
        model = model or self.WHISPER_MODEL
        rtf = self.WHISPER_RTF_FACTORS.get(model, 8.0)
        return int(duration_sec * rtf)


settings = Settings()
