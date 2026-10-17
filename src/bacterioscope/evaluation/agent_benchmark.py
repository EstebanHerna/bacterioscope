"""Live agent benchmark: grounding, fallback, latency, tokens, routed vs Ultra.

Wraps the real ``TokenFactoryClient`` in a recording proxy, so the shipped
``review_plate()`` runs unchanged while every Token Factory call is timed
and its real token usage captured. The same plates run twice: once with the
routing the agent core chooses (``routed``), once with every call forced to
the Ultra tier (``ultra_only``), which is the baseline the hackathon asks
routing to be compared against.

Cost is only computed from a caller-supplied price table: the official
Token Factory price page requires a signed-in session, so no price is
hardcoded here (see docs/EVALUATION_REPORT.md for how prices were sourced,
if any were).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from bacterioscope.agent.nemotron_client import (
    ChatCompletionResult,
    TokenFactoryConfigurationError,
    TokenFactoryRequestError,
)
from bacterioscope.evaluation.synthetic_benchmark import _quantile

if TYPE_CHECKING:
    from bacterioscope.agent.nemotron_client import TokenFactoryClient
    from bacterioscope.agent.validator import ValidationResult
    from bacterioscope.pipeline import AnalysisResult

TIERS = ("nano", "super", "ultra")
MODES = ("routed", "ultra_only")
_EXCLUDED_VARIANTS = re.compile(r"omni|vl\b|vision|embed|reward|guard|safety|base\b", re.I)


@dataclass(frozen=True)
class CallRecord:
    """One Token Factory call made during a review."""

    requested_tier: str
    used_tier: str
    model: str | None
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None
    error: str | None


class RecordingClient:
    """Duck-typed TokenFactoryClient proxy that records every call.

    Args:
        inner: The real client.
        force_tier: When set, every call goes to this tier regardless of
            what ``review_plate()`` routed it to (the Ultra-only baseline).
    """

    def __init__(self, inner: TokenFactoryClient, force_tier: str | None = None) -> None:
        self._inner = inner
        self._force_tier = force_tier
        self.calls: list[CallRecord] = []

    def model_for_tier(self, tier: str) -> str:
        return self._inner.model_for_tier(self._force_tier or tier)

    def chat(
        self, tier: str, messages: list[dict[str, str]], **kwargs: Any
    ) -> ChatCompletionResult:
        used = self._force_tier or tier
        started = time.perf_counter()
        try:
            result = self._inner.chat(used, messages, **kwargs)
        except (TokenFactoryConfigurationError, TokenFactoryRequestError) as exc:
            self.calls.append(CallRecord(
                tier, used, None, (time.perf_counter() - started) * 1000, None, None,
                type(exc).__name__,
            ))
            raise
        self.calls.append(CallRecord(
            tier, used, result.model, (time.perf_counter() - started) * 1000,
            result.prompt_tokens, result.completion_tokens, None,
        ))
        return result


@dataclass(frozen=True)
class AgentRunRecord:
    """One plate reviewed in one mode."""

    image: str
    mode: str
    status: str
    fallback_reason: str | None
    cited_evidence: int
    explanation_chars: int
    calls: tuple[CallRecord, ...] = field(default_factory=tuple)

    @property
    def latency_ms(self) -> float:
        return sum(call.latency_ms for call in self.calls)

    @property
    def tokens(self) -> tuple[int, int]:
        return (
            sum(call.prompt_tokens or 0 for call in self.calls),
            sum(call.completion_tokens or 0 for call in self.calls),
        )


def resolve_tier_models(
    available: Sequence[str], overrides: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Pick one live model ID per tier, refusing to guess between candidates.

    A tier resolves only when its override is set (and present in
    ``available``) or exactly one available ID mentions both "nemotron" and
    the tier name, after excluding multimodal/embedding/reward/safety/base
    variants.

    Args:
        available: Model IDs from ``TokenFactoryClient.list_models()``.
        overrides: Optional ``{tier: model_id}`` from NEBIUS_MODEL_* vars.

    Returns:
        ``{tier: model_id}`` for every tier.

    Raises:
        ValueError: A tier has zero or several candidates, or an override is
            not in the live catalog. The message lists the candidates.
    """
    overrides = {k: v for k, v in (overrides or {}).items() if v}
    resolved: dict[str, str] = {}
    for tier in TIERS:
        if tier in overrides:
            if overrides[tier] not in available:
                raise ValueError(f"{tier} override {overrides[tier]!r} is not in the live catalog")
            resolved[tier] = overrides[tier]
            continue
        candidates = [
            model for model in available
            if "nemotron" in model.lower()
            and tier in model.lower()
            and not _EXCLUDED_VARIANTS.search(model)
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"cannot resolve the {tier} tier unambiguously; candidates: {candidates}. "
                f"Set NEBIUS_MODEL_{tier.upper()} to one exact ID."
            )
        resolved[tier] = candidates[0]
    return resolved


def run_agent_benchmark(
    labeled: Sequence[tuple[str, AnalysisResult]],
    *,
    client: TokenFactoryClient,
    review: Callable[..., ValidationResult],
    organism: str,
    modes: Sequence[str] = MODES,
    public_alerts: Sequence[Any] = (),
) -> list[AgentRunRecord]:
    """Review every labelled plate once per mode, recording each call.

    Args:
        labeled: ``(image_name, antibiotic-labelled AnalysisResult)`` pairs.
        client: Configured real TokenFactoryClient.
        review: The review function, normally ``agent.orchestrator.review_plate``.
        organism: Organism passed to the review.
        modes: Any of ``routed`` and ``ultra_only``.
        public_alerts: Alerts fetched once beforehand and given identically
            to every review, so both modes see the same evidence (a live
            search per review could differ between modes and would not be a
            fair comparison).

    Returns:
        One AgentRunRecord per plate per mode.
    """
    records = []
    for mode in modes:
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
        for image, result in labeled:
            recorder = RecordingClient(client, force_tier="ultra" if mode == "ultra_only" else None)
            outcome = review(
                result, organism=organism, client=recorder, public_alerts=tuple(public_alerts)
            )
            explanation = outcome.report.get("model_explanation") or ""
            records.append(AgentRunRecord(
                image=image,
                mode=mode,
                status=outcome.status,
                fallback_reason=outcome.fallback_reason,
                cited_evidence=len(outcome.report.get("cited_evidence_ids", []) or []),
                explanation_chars=len(explanation),
                calls=tuple(recorder.calls),
            ))
    return records


def _cost(
    calls: Sequence[CallRecord], prices: Mapping[str, tuple[float, float]] | None
) -> float | None:
    if not prices:
        return None
    total = 0.0
    for call in calls:
        if call.model is None:
            continue
        if call.model not in prices:
            return None
        price_in, price_out = prices[call.model]
        total += (call.prompt_tokens or 0) * price_in / 1e6
        total += (call.completion_tokens or 0) * price_out / 1e6
    return total


def summarize_agent_runs(
    records: Sequence[AgentRunRecord],
    prices: Mapping[str, tuple[float, float]] | None = None,
) -> dict[str, Any]:
    """Aggregate agent runs per mode.

    Args:
        records: Output of ``run_agent_benchmark``.
        prices: Optional ``{model_id: (usd_per_M_input, usd_per_M_output)}``.

    Returns:
        ``{mode: {...}}`` with grounded rate, fallback reasons, latency
        p50/p95, token totals, tier mix, and cost per plate when priced.
    """
    summary: dict[str, Any] = {}
    for mode in sorted({r.mode for r in records}):
        rows = [r for r in records if r.mode == mode]
        latencies = [r.latency_ms for r in rows if r.calls]
        fallback_reasons: dict[str, int] = {}
        for r in rows:
            if r.status == "fallback":
                key = r.fallback_reason or "unknown"
                fallback_reasons[key] = fallback_reasons.get(key, 0) + 1
        tier_mix: dict[str, int] = {}
        for r in rows:
            for call in r.calls:
                tier_mix[call.used_tier] = tier_mix.get(call.used_tier, 0) + 1
        costs = [_cost(r.calls, prices) for r in rows]
        priced = [c for c in costs if c is not None]
        summary[mode] = {
            "plates": len(rows),
            "grounded": sum(r.status == "grounded_report" for r in rows),
            "grounded_rate": sum(r.status == "grounded_report" for r in rows) / len(rows),
            "fallback_reasons": fallback_reasons,
            "latency_ms_p50": _quantile(latencies, 0.5),
            "latency_ms_p95": _quantile(latencies, 0.95),
            "prompt_tokens": sum(r.tokens[0] for r in rows),
            "completion_tokens": sum(r.tokens[1] for r in rows),
            "tier_mix": tier_mix,
            "models": sorted({c.model for r in rows for c in r.calls if c.model}),
            "cost_usd_per_plate": (
                sum(priced) / len(priced) if priced and len(priced) == len(rows) else None
            ),
        }
    return summary
