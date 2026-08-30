from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and/or .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    PROJECT_NAME: str = "PhytoAgent"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Database Settings (Default to PostgreSQL asyncpg, customizable for SQLite async)
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/plant_agent"

    # OpenAI / LLM Model Settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL_NAME: str = "gpt-4o"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance.
    """
    return Settings()


settings = get_settings()
