"""Tests for agent.nemotron_client.TokenFactoryClient.

Every test injects a fake client double; none requires the real 'openai'
package to be installed or makes a network call, matching the project's
mock-provider-calls-in-CI rule (docs/TEAM_EXECUTION_PLAN.md).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from bacterioscope.agent.nemotron_client import (
    TokenFactoryClient,
    TokenFactoryConfigurationError,
    TokenFactoryRequestError,
)


@dataclass
class _FakeMessage:
    content: str | None


@dataclass
class _FakeChoice:
    message: _FakeMessage
    finish_reason: str | None = "stop"


@dataclass
class _FakeChatResponse:
    choices: list[_FakeChoice]


@dataclass
class _FakeModel:
    id: str


@dataclass
class _FakeModelsResponse:
    data: list[_FakeModel]


class _FakeCompletions:
    def __init__(self, response: _FakeChatResponse) -> None:
        self._response = response
        self.last_kwargs: dict[str, object] | None = None

    def create(self, **kwargs: object) -> _FakeChatResponse:
        self.last_kwargs = kwargs
        return self._response


class _FakeChat:
    def __init__(self, completions: _FakeCompletions) -> None:
        self.completions = completions


class _FakeModels:
    def __init__(self, response: _FakeModelsResponse) -> None:
        self._response = response

    def list(self) -> _FakeModelsResponse:
        return self._response


class _FakeOpenAIClient:
    def __init__(self, chat_response: _FakeChatResponse, models: list[str]) -> None:
        self.chat = _FakeChat(_FakeCompletions(chat_response))
        self.models = _FakeModels(_FakeModelsResponse([_FakeModel(m) for m in models]))


def _client(**overrides: object) -> TokenFactoryClient:
    defaults: dict[str, object] = {
        "api_key": "test-key",
        "models": {"nano": "vendor/nano", "super": "vendor/super", "ultra": "vendor/ultra"},
    }
    defaults.update(overrides)
    return TokenFactoryClient(**defaults)  # type: ignore[arg-type]


class TestConfigured:
    def test_true_when_key_present(self) -> None:
        assert _client().configured is True

    def test_false_when_key_missing(self) -> None:
        assert _client(api_key="").configured is False

    def test_false_when_key_only_whitespace(self) -> None:
        assert _client(api_key="   ").configured is False


class TestModelForTier:
    def test_returns_configured_model(self) -> None:
        assert _client().model_for_tier("nano") == "vendor/nano"

    def test_raises_on_unknown_tier(self) -> None:
        with pytest.raises(ValueError, match="tier must be one of"):
            _client().model_for_tier("medium")

    def test_raises_configuration_error_when_tier_unset(self) -> None:
        client = _client(models={"nano": "", "super": "vendor/super", "ultra": "vendor/ultra"})
        with pytest.raises(TokenFactoryConfigurationError, match="NEBIUS_MODEL_NANO"):
            client.model_for_tier("nano")


class TestChat:
    def test_raises_configuration_error_without_api_key(self) -> None:
        client = _client(api_key="")
        with pytest.raises(TokenFactoryConfigurationError):
            client.chat("nano", [{"role": "user", "content": "hi"}])

    def test_returns_content_on_success(self) -> None:
        fake = _FakeOpenAIClient(
            _FakeChatResponse([_FakeChoice(_FakeMessage("hello"))]), models=[]
        )
        client = _client(client=fake)
        result = client.chat("nano", [{"role": "user", "content": "hi"}])
        assert result.content == "hello"
        assert result.tier == "nano"
        assert result.model == "vendor/nano"
        assert result.finish_reason == "stop"

    def test_passes_the_resolved_model_to_the_sdk(self) -> None:
        fake = _FakeOpenAIClient(
            _FakeChatResponse([_FakeChoice(_FakeMessage("hello"))]), models=[]
        )
        client = _client(client=fake)
        client.chat("super", [{"role": "user", "content": "hi"}])
        assert fake.chat.completions.last_kwargs is not None
        assert fake.chat.completions.last_kwargs["model"] == "vendor/super"

    def test_raises_request_error_on_empty_choices(self) -> None:
        fake = _FakeOpenAIClient(_FakeChatResponse([]), models=[])
        client = _client(client=fake)
        with pytest.raises(TokenFactoryRequestError, match="no choices"):
            client.chat("nano", [{"role": "user", "content": "hi"}])

    def test_empty_content_becomes_empty_string_not_none(self) -> None:
        fake = _FakeOpenAIClient(
            _FakeChatResponse([_FakeChoice(_FakeMessage(None))]), models=[]
        )
        client = _client(client=fake)
        result = client.chat("nano", [{"role": "user", "content": "hi"}])
        assert result.content == ""


class TestListModels:
    def test_returns_sorted_model_ids(self) -> None:
        fake = _FakeOpenAIClient(
            _FakeChatResponse([]), models=["vendor/b-model", "vendor/a-model"]
        )
        client = _client(client=fake)
        assert client.list_models() == ["vendor/a-model", "vendor/b-model"]

    def test_raises_configuration_error_without_api_key(self) -> None:
        client = _client(api_key="")
        with pytest.raises(TokenFactoryConfigurationError):
            client.list_models()
