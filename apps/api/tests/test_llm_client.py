"""The OpenRouter client and the LLM settings: no network, the client is only built."""

import openai
import pytest

from novoya_api.config import Settings, get_settings
from novoya_api.shared.infrastructure.llm.client import (
    OPENROUTER_BASE_URL,
    create_llm_client,
    get_llm_client,
    get_model_pause,
    get_orchestrator,
)
from novoya_api.shared.infrastructure.llm.errors import LLMError


def test_openrouter_base_url_points_at_the_v1_api():
    assert OPENROUTER_BASE_URL == "https://openrouter.ai/api/v1"


def test_client_is_an_async_openai_client_pointed_at_openrouter():
    client = create_llm_client("sk-or-test")

    assert isinstance(client, openai.AsyncOpenAI)
    assert str(client.base_url) == "https://openrouter.ai/api/v1/"


def test_client_uses_the_given_api_key():
    assert create_llm_client("sk-or-test").api_key == "sk-or-test"


def test_client_never_retries_and_times_out_after_30_seconds():
    # The orchestrator falls back to other models and pauses on a 429: SDK retries only add
    # delay (on a 429 the SDK would sleep for Retry-After first).
    client = create_llm_client("sk-or-test")

    assert client.max_retries == 0
    assert client.timeout == 30


def test_client_without_api_key_raises_llm_error():
    with pytest.raises(LLMError):
        create_llm_client(None)


def test_client_with_empty_api_key_raises_llm_error():
    with pytest.raises(LLMError):
        create_llm_client("")


def test_settings_have_llm_defaults(monkeypatch):
    monkeypatch.delenv("NOVOYA_LLM_MODEL", raising=False)
    monkeypatch.delenv("NOVOYA_LLM_FALLBACK_MODELS", raising=False)
    monkeypatch.delenv("NOVOYA_OPENROUTER_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.openrouter_api_key is None
    assert settings.llm_model == "nvidia/nemotron-3-ultra-550b-a55b:free"
    assert settings.llm_fallback_models == [
        "minimax/minimax-m3.1-flash:free",
        "nvidia/nemotron-3.5-super-vl:free",
        "poolside/laguna-s-2.1:free",
    ]


def test_settings_read_openrouter_api_key_as_secret(monkeypatch):
    monkeypatch.setenv("NOVOYA_OPENROUTER_API_KEY", "sk-or-secret")

    settings = Settings(_env_file=None)

    assert settings.openrouter_api_key.get_secret_value() == "sk-or-secret"
    assert "sk-or-secret" not in repr(settings)


def test_settings_read_fallback_models_as_a_json_list(monkeypatch):
    monkeypatch.setenv("NOVOYA_LLM_FALLBACK_MODELS", '["a/model:free", "b/model:free"]')

    assert Settings(_env_file=None).llm_fallback_models == ["a/model:free", "b/model:free"]


def test_empty_fallback_models_means_no_fallback(monkeypatch):
    monkeypatch.setenv("NOVOYA_LLM_FALLBACK_MODELS", "")

    assert Settings(_env_file=None).llm_fallback_models == []


def test_orchestrator_tries_the_model_then_the_fallbacks(monkeypatch):
    monkeypatch.setenv("NOVOYA_OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setenv("NOVOYA_LLM_MODEL", "main/model")
    monkeypatch.setenv("NOVOYA_LLM_FALLBACK_MODELS", '["backup/model"]')
    get_settings.cache_clear()
    get_llm_client.cache_clear()
    try:
        assert get_orchestrator()._models == ["main/model", "backup/model"]
    finally:
        get_settings.cache_clear()
        get_llm_client.cache_clear()


def test_every_orchestrator_shares_one_pause(monkeypatch):
    monkeypatch.setenv("NOVOYA_OPENROUTER_API_KEY", "sk-or-test")
    get_settings.cache_clear()
    get_llm_client.cache_clear()
    try:
        first, second = get_orchestrator(), get_orchestrator()

        assert first._pause is second._pause is get_model_pause()
    finally:
        get_settings.cache_clear()
        get_llm_client.cache_clear()
