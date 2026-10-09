"""Token Factory (Nebius) chat-completions client for the Nemotron agent core.

Owned by Persona 1. No Nemotron model ID is hardcoded here: Nebius Token
Factory's exact Nemotron 3 Nano/Super/Ultra model strings are not published
on a stable, versioned reference as of this writing -- only the API shape is
confirmed (OpenAI-compatible, base URL https://api.tokenfactory.nebius.com/v1/,
Bearer auth; docs.tokenfactory.nebius.com). Call list_models() once real
credentials are configured and copy the exact strings into NEBIUS_MODEL_NANO/
_SUPER/_ULTRA -- do not guess them from a third-party listing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
_ENV_API_KEY = "NEBIUS_API_KEY"
_ENV_BASE_URL = "NEBIUS_BASE_URL"
_ENV_MODEL_BY_TIER = {
    "nano": "NEBIUS_MODEL_NANO",
    "super": "NEBIUS_MODEL_SUPER",
    "ultra": "NEBIUS_MODEL_ULTRA",
}


class TokenFactoryConfigurationError(RuntimeError):
    """Raised when the client has no API key, or a tier has no model string set."""


class TokenFactoryRequestError(RuntimeError):
    """Raised when a Token Factory request fails or returns an unusable response."""


def _openai_error_types() -> tuple[type[BaseException], ...]:
    """Resolve openai.OpenAIError lazily for a narrow except clause.

    Returns an empty tuple (matches nothing, never raises on its own) when
    the 'openai' package is not installed, which only matters for a test
    double injected via the ``client`` constructor argument -- the real SDK
    call path above already fails closed with TokenFactoryConfigurationError
    before reaching this point if 'openai' is missing.
    """
    try:
        from openai import OpenAIError
    except ImportError:
        return ()
    return (OpenAIError,)


@dataclass(frozen=True)
class ChatCompletionResult:
    """One chat-completion response, reduced to what the agent core needs."""

    tier: str
    model: str
    content: str
    finish_reason: str | None


class TokenFactoryClient:
    """Thin wrapper over the OpenAI-compatible Nebius Token Factory API.

    The ``openai`` package is imported lazily, the same pattern
    ``detection/detector.py`` uses for ``ultralytics``, so importing this
    module never requires the package to be installed. Pass ``client`` to
    inject a test double without installing or calling the real SDK.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        models: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
        client: Any = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.getenv(_ENV_API_KEY, "")
        self._base_url = (
            base_url if base_url is not None else os.getenv(_ENV_BASE_URL, DEFAULT_BASE_URL)
        )
        self._models = (
            models
            if models is not None
            else {tier: os.getenv(env_name, "") for tier, env_name in _ENV_MODEL_BY_TIER.items()}
        )
        self._timeout_seconds = timeout_seconds
        self._client = client

    @property
    def configured(self) -> bool:
        """True when an API key is set. Does not confirm the key is valid."""
        return bool(self._api_key.strip())

    def model_for_tier(self, tier: str) -> str:
        """Return the configured model string for one difficulty tier.

        Args:
            tier: One of 'nano', 'super', 'ultra'.

        Returns:
            The model ID string from the matching NEBIUS_MODEL_* env var.

        Raises:
            ValueError: tier is not one of the three known tiers.
            TokenFactoryConfigurationError: No model string is set for this tier.
        """
        if tier not in _ENV_MODEL_BY_TIER:
            raise ValueError(f"tier must be one of {sorted(_ENV_MODEL_BY_TIER)}")
        model = self._models.get(tier, "")
        if not model.strip():
            env_name = _ENV_MODEL_BY_TIER[tier]
            raise TokenFactoryConfigurationError(
                f"{env_name} is not set; run list_models() against your own account "
                "and copy the exact model string -- do not guess it"
            )
        return model

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.configured:
            raise TokenFactoryConfigurationError(f"{_ENV_API_KEY} is not configured")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise TokenFactoryConfigurationError(
                "the 'openai' package is required; install with pip install -e '.[agent]'"
            ) from exc
        self._client = OpenAI(
            api_key=self._api_key, base_url=self._base_url, timeout=self._timeout_seconds
        )
        return self._client

    def list_models(self) -> list[str]:
        """Return every model ID visible to this API key, straight from Token Factory.

        Run this once real credentials are configured; it is the source of
        truth for the exact Nemotron tier strings, not any third-party list.
        """
        client = self._get_client()
        try:
            response = client.models.list()
        except _openai_error_types() as exc:
            raise TokenFactoryRequestError(f"Token Factory model list failed: {exc}") from exc
        return sorted(model.id for model in response.data)

    def chat(
        self, tier: str, messages: list[dict[str, str]], *, max_tokens: int = 1024
    ) -> ChatCompletionResult:
        """Call one chat-completions request on the given difficulty tier.

        Args:
            tier: One of 'nano', 'super', 'ultra' (docs/AGENT_ARCHITECTURE.md routing).
            messages: OpenAI-style role/content message list.
            max_tokens: Upper bound on the completion length.

        Returns:
            ChatCompletionResult with the raw text content.

        Raises:
            TokenFactoryConfigurationError: Missing API key or model for this tier.
            TokenFactoryRequestError: The request failed or returned no choice.
        """
        model = self.model_for_tier(tier)
        client = self._get_client()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                timeout=self._timeout_seconds,
            )
        except _openai_error_types() as exc:
            raise TokenFactoryRequestError(f"Token Factory request failed: {exc}") from exc
        if not response.choices:
            raise TokenFactoryRequestError("Token Factory returned no choices")
        choice = response.choices[0]
        content = choice.message.content or ""
        return ChatCompletionResult(
            tier=tier, model=model, content=content, finish_reason=choice.finish_reason
        )
