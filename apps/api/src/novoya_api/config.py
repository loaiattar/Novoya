import json
from functools import lru_cache
from typing import Annotated

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables (prefix NOVOYA_) or a .env file."""

    model_config = SettingsConfigDict(env_prefix="NOVOYA_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+asyncpg://novoya:novoya@localhost:5432/novoya"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Accounts: sessions, passwords, emails, Google
    frontend_url: str = "http://localhost:5173"  # links in emails point to the web app
    api_public_url: str = "http://localhost:8000"  # builds the Google redirect URI
    google_client_id: str | None = None  # without both, sign-in with Google is off (#15)
    google_client_secret: SecretStr | None = None
    session_cookie_secure: bool = False  # true in production (HTTPS): Secure + __Host- prefix
    session_idle_ttl_days: int = 7
    session_absolute_ttl_days: int = 30
    require_verified_email: bool = True
    smtp_host: str = "localhost"  # Mailpit locally
    smtp_port: int = 1025
    smtp_username: str | None = None  # a real provider (Brevo, SES...) needs these three
    smtp_password: SecretStr | None = None
    smtp_start_tls: bool = False
    mail_from: str = "Novoya <no-reply@novoya.local>"
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 65536

    # The DÉTOUR export an admin uploads from the back office (#132). The first export is
    # well under this; a bigger one is refused with 413 before it is all received.
    detour_max_bytes: int = 20_000_000

    # LLM through OpenRouter (#22). Free models; the fallbacks are tried in order.
    openrouter_api_key: SecretStr | None = None
    llm_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    llm_fallback_models: Annotated[list[str], NoDecode] = [
        "minimax/minimax-m3.1-flash:free",
        "nvidia/nemotron-3.5-super-vl:free",
        "poolside/laguna-s-2.1:free",
    ]

    @field_validator("llm_fallback_models", mode="before")
    @classmethod
    def _parse_fallback_models(cls, value: object) -> object:
        """A JSON list from the environment; empty means no fallback."""
        if isinstance(value, str):
            return json.loads(value) if value.strip() else []
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
