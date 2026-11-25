from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables (and backend/.env)."""

    database_url: str = "postgresql+psycopg://axiom:axiom@localhost:5432/axiom"

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
