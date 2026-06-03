from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Literal

PLACEHOLDER_SECRET_MARKERS = ("change-me", "in-production", "replace-with", "your-")


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

        return self

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://sourcecast:sourcecast_dev@localhost:5432/sourcecast"
    )

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

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_PROVIDER: Literal["local", "supabase", "s3"] = "local"
    AUDIO_STORAGE_POLICY: Literal[
        "DELETE_AFTER_TRANSCRIPTION", "RETAIN"
    ] = "DELETE_AFTER_TRANSCRIPTION"

    # ── AI / RAG ──────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_PROVIDER: Literal["extractive", "groq"] = "extractive"
    LLM_MODEL: str = "llama-3.1-8b-instant"
    LLM_TIMEOUT_SECONDS: int = 30
    DEFAULT_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    DEFAULT_QDRANT_COLLECTION: str = "source_chunks_v1_minilm_384"
    WHISPER_MODEL: str = "base"

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
