from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables (prefix NOVOYA_) or a .env file."""

    model_config = SettingsConfigDict(env_prefix="NOVOYA_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://novoya:novoya@localhost:5432/novoya"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
