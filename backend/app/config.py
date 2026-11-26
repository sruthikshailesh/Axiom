from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DATABASE_URL = "postgresql+psycopg://axiom:axiom@localhost:5432/axiom"
LOCAL_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

# Managed Postgres providers (Render among them) hand out a plain DSN. SQLAlchemy
# needs the driver named explicitly, so both forms are rewritten to psycopg 3.
POSTGRES_PREFIXES = ("postgres://", "postgresql://")


def normalise_database_url(url: str) -> str:
    """Return a SQLAlchemy URL that uses the psycopg 3 driver."""
    value = url.strip()
    for prefix in POSTGRES_PREFIXES:
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix) :]
    return value


class Settings(BaseSettings):
    """Application settings, read from environment variables (and backend/.env)."""

    database_url: str = LOCAL_DATABASE_URL

    # Comma-separated browser origins allowed to call this API. Never a wildcard:
    # credentials (the Bearer token) are sent with every request.
    cors_origins: str = LOCAL_CORS_ORIGINS

    llm_provider: str = "openai"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: str = "openai/gpt-oss-20b"

    # Single local account. All three are optional so the app still boots
    # without them; sign-in then answers 503 instead of failing at import.
    axiom_username: Optional[str] = None
    axiom_password_hash: Optional[str] = None
    axiom_secret: Optional[str] = None
    axiom_token_hours: int = 12

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        return normalise_database_url(value)

    @property
    def cors_origin_list(self) -> List[str]:
        """The configured origins, trimmed, with empty entries dropped."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
