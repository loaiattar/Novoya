from functools import lru_cache

from openai import AsyncOpenAI

from novoya_api.config import get_settings
from novoya_api.shared.infrastructure.llm.errors import LLMError
from novoya_api.shared.infrastructure.llm.orchestrator import Orchestrator
from novoya_api.shared.infrastructure.llm.pause import ModelPause

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def create_llm_client(api_key: str | None) -> AsyncOpenAI:
    """OpenRouter speaks the OpenAI API, so the official SDK works with another base URL."""
    if not api_key:
        raise LLMError("NOVOYA_OPENROUTER_API_KEY is not set")
    # Calls happen during a request. No SDK retry: the orchestrator falls back to the next
    # model itself, and on a 429 the SDK would sleep for Retry-After (up to a minute) before
    # the orchestrator could pause the model and fall back at once (#106).
    return AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key, timeout=30, max_retries=0)


@lru_cache
def get_llm_client() -> AsyncOpenAI:
    key = get_settings().openrouter_api_key
    return create_llm_client(key.get_secret_value() if key else None)


@lru_cache
def get_model_pause() -> ModelPause:
    """One pause for the whole process: every orchestrator shares the key's quota."""
    return ModelPause()


def get_orchestrator(
    deadline_seconds: float = 90, model_timeout_seconds: float | None = None
) -> Orchestrator:
    """The orchestrator with the configured model, then its fallbacks in order.

    Raises LLMError without an API key: call it inside the adapter's try, not as a
    FastAPI dependency, so the use case can still fall back."""
    settings = get_settings()
    return Orchestrator(
        get_llm_client(),
        [settings.llm_model, *settings.llm_fallback_models],
        deadline_seconds=deadline_seconds,
        model_timeout_seconds=model_timeout_seconds,
        pause=get_model_pause(),
    )
