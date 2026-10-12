"""Integration test for agent.orchestrator.review_plate: the full real chain.

Runs normalize_ast_observations -> the three real Persona 2 rule tools ->
assemble_evidence -> a fake TokenFactoryClient (no network, no credentials)
-> validate_and_render, and checks the result actually satisfies the real
agent-review-v1 schema. This is the one test that exercises every module
built so far together, on data shaped like what the pipeline really emits.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from bacterioscope.agent.nemotron_client import TokenFactoryClient
from bacterioscope.agent.orchestrator import review_plate
from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.pipeline import AnalysisResult
from bacterioscope.segmentation.watershed import ZoneResult


def _disk(i: int) -> DiskResult:
    return DiskResult(
        label=f"disk_{i}", center_x=100 + i * 50, center_y=100,
        radius_px=15, confidence=1.0, bbox=(85 + i * 50, 85, 115 + i * 50, 115),
    )


def _zone(i: int, mm: float) -> ZoneResult:
    return ZoneResult(
        disk_label=f"disk_{i}", center_x=100 + i * 50, center_y=100,
        radius_px=20.0, diameter_px=40.0, diameter_mm=mm,
        area_px=1256.0, circularity=0.9, mask=None,
    )


def _cls(antibiotic: str, mm: float, category: str) -> SusceptibilityResult:
    return SusceptibilityResult(
        antibiotic=antibiotic, zone_diameter_mm=mm, category=category,
        breakpoints={} if category == "UNKNOWN" else {"S": 20.0, "R": 15.0},
    )


def _result() -> AnalysisResult:
    classifications = [
        _cls("ciprofloxacin", 26.0, "S"),
        _cls("meropenem", 10.0, "R"),
        _cls("disk_2", 8.0, "UNKNOWN"),
    ]
    n = len(classifications)
    return AnalysisResult(
        image_path="/tmp/test.jpg", plate_diameter_px=900.0, px_per_mm=10.0,
        disks=[_disk(i) for i in range(n)],
        zones=[_zone(i, c.zone_diameter_mm) for i, c in enumerate(classifications)],
        classifications=classifications,
        flags=[[], ["low_circularity"], []],
        breakpoint_table_version="CLSI M100-Ed33 2023",
        analysis_id="abc123", software_version="0.1.0", commit_hash="deadbee",
        image_sha256="x" * 64,
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


class _FakeCompletions:
    def __init__(self, response: _FakeChatResponse) -> None:
        self._response = response

    def create(self, **kwargs: object) -> _FakeChatResponse:
        return self._response


class _FakeChat:
    def __init__(self, response: _FakeChatResponse) -> None:
        self.completions = _FakeCompletions(response)


class _FakeOpenAIClient:
    def __init__(self, response: _FakeChatResponse) -> None:
        self.chat = _FakeChat(response)


def _configured_client(content: str) -> TokenFactoryClient:
    fake = _FakeOpenAIClient(_FakeChatResponse([_FakeChoice(_FakeMessage(content))]))
    return TokenFactoryClient(
        api_key="test-key",
        models={"nano": "vendor/nano", "super": "vendor/super", "ultra": "vendor/ultra"},
        client=fake,
    )


class TestReviewPlateSuccess:
    def test_well_formed_model_response_yields_grounded_report(self) -> None:
        content = json.dumps({"explanation": "No concerning findings.", "evidence_ids": []})
        client = _configured_client(content)
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        assert outcome.status == "grounded_report"
        assert outcome.report["model_explanation"] == "No concerning findings."

    def test_report_measurement_keeps_the_unknown_disk(self) -> None:
        content = json.dumps({"explanation": "ok", "evidence_ids": []})
        client = _configured_client(content)
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        observations = outcome.report["measurement"]["observations"]
        assert len(observations) == 3
        unresolved = [o for o in observations if not o["included_in_rule_evaluation"]]
        assert len(unresolved) == 1
        assert unresolved[0]["exclusion_reason"] == "unresolved_antibiotic_identity"

    def test_empty_catalog_means_no_rule_findings_today(self) -> None:
        content = json.dumps({"explanation": "ok", "evidence_ids": []})
        client = _configured_client(content)
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        assert outcome.report["rule_findings"] == []
        assert outcome.report["catalog_status"]["intrinsic_resistance"] == "no_rules_configured"

    def test_esbl_screen_is_not_run(self) -> None:
        content = json.dumps({"explanation": "ok", "evidence_ids": []})
        client = _configured_client(content)
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        assert outcome.report["esbl_screen"] is None


class TestReviewPlateFallback:
    def test_unconfigured_client_falls_back(self) -> None:
        client = TokenFactoryClient(
            api_key="",
            models={"nano": "vendor/nano", "super": "vendor/super", "ultra": "vendor/ultra"},
        )
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        assert outcome.status == "fallback"
        assert outcome.fallback_reason == "token_factory_unavailable"
        assert outcome.report["model_explanation"] is None

    def test_empty_choices_falls_back(self) -> None:
        fake = _FakeOpenAIClient(_FakeChatResponse([]))
        client = TokenFactoryClient(
            api_key="test-key",
            models={"nano": "vendor/nano", "super": "vendor/super", "ultra": "vendor/ultra"},
            client=fake,
        )
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        assert outcome.status == "fallback"
        assert outcome.fallback_reason == "token_factory_unavailable"

    def test_malformed_model_output_falls_back_but_keeps_real_measurement(self) -> None:
        client = _configured_client("not json{{")
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        assert outcome.status == "fallback"
        assert outcome.fallback_reason == "model_output_not_json"
        first_obs = outcome.report["measurement"]["observations"][0]
        assert first_obs["antibiotic_code"] == "ciprofloxacin"

    def test_fallback_report_still_requires_human_review(self) -> None:
        client = _configured_client("not json{{")
        outcome = review_plate(_result(), organism="Escherichia coli", client=client)
        assert outcome.report["requires_human_review"] is True
