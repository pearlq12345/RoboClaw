"""Tests for provider factory helpers used by the Web settings flow."""

from __future__ import annotations

from pathlib import Path

import pytest

from roboclaw.config.loader import save_config
from roboclaw.config.schema import Config
from roboclaw.providers.custom_provider import CustomProvider
from roboclaw.providers.factory import ConfigBackedProvider, ProviderConfigurationError, build_provider


def test_build_provider_requires_configuration() -> None:
    config = Config()

    with pytest.raises(ProviderConfigurationError):
        build_provider(config)


def test_build_provider_supports_custom_api_base() -> None:
    config = Config()
    config.agents.defaults.provider = "custom"
    config.agents.defaults.model = "custom/local-model"
    config.providers.custom.api_base = "http://127.0.0.1:8000/v1"

    provider = build_provider(config)

    assert isinstance(provider, CustomProvider)


def test_build_provider_custom_requires_api_base() -> None:
    config = Config()
    config.agents.defaults.provider = "custom"
    config.agents.defaults.model = "custom/local-model"

    with pytest.raises(ProviderConfigurationError):
        build_provider(config)


@pytest.mark.asyncio
async def test_config_backed_provider_returns_helpful_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    save_config(Config(), config_path)

    provider = ConfigBackedProvider(config_path)
    response = await provider.chat_with_retry(
        messages=[{"role": "user", "content": "hello"}],
        model="anthropic/claude-opus-4-5",
    )

    assert response.finish_reason == "error"
    assert response.content is not None
    assert "Provider is not configured" in response.content
