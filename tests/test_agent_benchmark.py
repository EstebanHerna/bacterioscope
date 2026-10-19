"""Tests for evaluation.agent_benchmark (no network: fake clients only)."""

from __future__ import annotations

from typing import Any

import pytest

from bacterioscope.agent.nemotron_client import ChatCompletionResult, TokenFactoryRequestError
from bacterioscope.agent.validator import ValidationResult
from bacterioscope.evaluation.agent_benchmark import (
    CallRecord,
    RecordingClient,
    resolve_tier_models,
    run_agent_benchmark,
    summarize_agent_runs,
)


class _FakeInner:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.tiers: list[str] = []

    def model_for_tier(self, tier: str) -> str:
        return f"vendor/{tier}"

    def chat(
        self, tier: str, messages: list[dict[str, str]], **kwargs: Any
    ) -> ChatCompletionResult:
        self.tiers.append(tier)
        if self.fail:
            raise TokenFactoryRequestError("boom")
        return ChatCompletionResult(tier, f"vendor/{tier}", "{}", "stop", 100, 20)


class TestRecordingClient:
    def test_records_tokens_and_model(self) -> None:
        recorder = RecordingClient(_FakeInner())  # type: ignore[arg-type]
        recorder.chat("super", [])
        call = recorder.calls[0]
        assert (call.used_tier, call.model, call.prompt_tokens, call.completion_tokens) == (
            "super", "vendor/super", 100, 20,
        )
        assert call.error is None

    def test_force_tier_overrides_routing(self) -> None:
        inner = _FakeInner()
        recorder = RecordingClient(inner, force_tier="ultra")  # type: ignore[arg-type]
        recorder.chat("nano", [])
        assert inner.tiers == ["ultra"]
        assert recorder.calls[0].requested_tier == "nano"
        assert recorder.model_for_tier("nano") == "vendor/ultra"

    def test_records_then_reraises_errors(self) -> None:
        recorder = RecordingClient(_FakeInner(fail=True))  # type: ignore[arg-type]
        with pytest.raises(TokenFactoryRequestError):
            recorder.chat("super", [])
        assert recorder.calls[0].error == "TokenFactoryRequestError"


class TestResolveTierModels:
    _CATALOG = [
        "nvidia/Nemotron-3-Nano-30B-A3B",
        "nvidia/Nemotron-3-Nano-Omni",
        "nvidia/nemotron-3-super-120b-a12b",
        "nvidia/Nemotron-3-Ultra-550b-a55b",
        "meta-llama/Llama-3.3-70B-Instruct",
    ]

    def test_unique_candidates_resolve(self) -> None:
        models = resolve_tier_models(self._CATALOG)
        assert models == {
            "nano": "nvidia/Nemotron-3-Nano-30B-A3B",
            "super": "nvidia/nemotron-3-super-120b-a12b",
            "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
        }

    def test_ambiguous_tier_refuses_to_guess(self) -> None:
        with pytest.raises(ValueError, match="nano"):
            resolve_tier_models([*self._CATALOG, "nvidia/Nemotron-3-Nano-9B"])

    def test_override_wins_when_in_catalog(self) -> None:
        models = resolve_tier_models(self._CATALOG, {"nano": "nvidia/Nemotron-3-Nano-Omni"})
        assert models["nano"] == "nvidia/Nemotron-3-Nano-Omni"

    def test_override_missing_from_catalog_raises(self) -> None:
        with pytest.raises(ValueError, match="not in the live catalog"):
            resolve_tier_models(self._CATALOG, {"ultra": "nvidia/does-not-exist"})


def _review(result: Any, *, organism: str, client: Any, public_alerts: Any) -> ValidationResult:
    client.chat("super", [])
    report = {"model_explanation": "ok", "cited_evidence_ids": ["a"]}
    return ValidationResult("grounded_report", report, None)


class TestRunAndSummarize:
    def test_both_modes_run_every_plate(self) -> None:
        inner = _FakeInner()
        records = run_agent_benchmark(
            [("a.png", object()), ("b.png", object())],
            client=inner,  # type: ignore[arg-type]
            review=_review, organism="E. coli",
        )
        assert [(r.image, r.mode) for r in records] == [
            ("a.png", "routed"), ("b.png", "routed"),
            ("a.png", "ultra_only"), ("b.png", "ultra_only"),
        ]
        assert inner.tiers == ["super", "super", "ultra", "ultra"]
        assert all(r.cited_evidence == 1 for r in records)

    def test_unknown_mode_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown mode"):
            run_agent_benchmark([], client=_FakeInner(),  # type: ignore[arg-type]
                                review=_review, organism="x", modes=["cheapest"])

    def test_summary_cost_only_with_prices(self) -> None:
        records = run_agent_benchmark(
            [("a.png", object())], client=_FakeInner(),  # type: ignore[arg-type]
            review=_review, organism="x", modes=["routed"],
        )
        assert summarize_agent_runs(records)["routed"]["cost_usd_per_plate"] is None
        priced = summarize_agent_runs(records, {"vendor/super": (1.0, 3.0)})
        assert priced["routed"]["cost_usd_per_plate"] == pytest.approx((100 * 1 + 20 * 3) / 1e6)
        assert priced["routed"]["grounded_rate"] == 1.0
        assert priced["routed"]["tier_mix"] == {"super": 1}

    def test_unpriced_model_means_no_cost(self) -> None:
        records = run_agent_benchmark(
            [("a.png", object())], client=_FakeInner(),  # type: ignore[arg-type]
            review=_review, organism="x", modes=["routed"],
        )
        assert summarize_agent_runs(records, {"other/model": (1.0, 1.0)})["routed"][
            "cost_usd_per_plate"
        ] is None


def test_call_record_is_immutable() -> None:
    record = CallRecord("nano", "nano", "m", 1.0, 1, 1, None)
    with pytest.raises(AttributeError):
        record.latency_ms = 2.0  # type: ignore[misc]
