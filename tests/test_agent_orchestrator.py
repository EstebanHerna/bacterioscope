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

import pytest

from bacterioscope.agent.nemotron_client import TokenFactoryClient
from bacterioscope.agent.orchestrator import review_plate
from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.integrations.tavily import PublicAlert, TavilySearchError
from bacterioscope.pipeline import AnalysisResult
from bacterioscope.rules import ESBLScreenContext, ZoneObservation
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


class _FakeTavilySearch:
    def __init__(self, *, results: list[PublicAlert] | None = None, fail: bool = False) -> None:
        self._results = results or []
        self._fail = fail

    def search_amr_alerts(self, source: str) -> list[PublicAlert]:
        if self._fail:
            raise TavilySearchError("test failure")
        return self._results


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
        assert len(unresolved) == 2
        by_index = {o["disk_index"]: o["exclusion_reason"] for o in unresolved}
        assert by_index[1] == "measurement_quality_flags:low_circularity"
        assert by_index[2] == "unresolved_antibiotic_identity"

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

    def test_rule_standard_is_reported_separately_from_measurement_standard(self) -> None:
        client = _configured_client(json.dumps({"explanation": "ok", "evidence_ids": []}))
        outcome = review_plate(
            _result(), organism="Escherichia coli", client=client,
            rule_standard="CLSI M100-Ed36 2026",
        )
        assert outcome.report["measurement"]["standard"] == "CLSI M100-Ed33 2023"
        assert outcome.report["rule_standard"] == "CLSI M100-Ed36 2026"

    def test_empty_rule_standard_is_not_silently_replaced(self) -> None:
        client = _configured_client(json.dumps({"explanation": "ok", "evidence_ids": []}))
        with pytest.raises(ValueError, match="rule_standard or result.breakpoint_table_version"):
            review_plate(
                _result(), organism="Escherichia coli", client=client, rule_standard=" "
            )

    def test_ed36_esbl_screen_is_explicit_and_fail_closed(self) -> None:
        client = _configured_client(json.dumps({"explanation": "ok", "evidence_ids": []}))
        context = ESBLScreenContext(
            method="disk diffusion", medium="MHA", temperature_c=35,
            incubation_hours=17, atmosphere="ambient air",
            standard_disk_diffusion_procedure=True,
        )
        outcome = review_plate(
            _result(), organism="Escherichia coli", client=client,
            esbl_standard="CLSI M100-Ed36 2026", esbl_context=context,
            esbl_observations=[ZoneObservation("ceftazidime", 30, 20.0, True)],
        )
        assert outcome.report["esbl_screen"]["standard"] == "CLSI M100-Ed36 2026"
        assert outcome.report["esbl_screen"]["status"] == "screen_rules_unavailable"
        assert outcome.report["esbl_screen"]["screen_signal"] is None

    def test_esbl_inputs_without_explicit_standard_are_rejected(self) -> None:
        client = _configured_client(json.dumps({"explanation": "ok", "evidence_ids": []}))
        try:
            review_plate(
                _result(), organism="Escherichia coli", client=client,
                esbl_observations=[ZoneObservation("ceftazidime", 30, 20.0, True)],
            )
        except ValueError as exc:
            assert "esbl_standard is required" in str(exc)
        else:
            raise AssertionError("missing ESBL edition must not be silently inferred")

    def test_tavily_results_and_availability_are_in_report(self) -> None:
        client = _configured_client(json.dumps({"explanation": "ok", "evidence_ids": [
            "https://ins.gov.co/alerta",
        ]}))
        alert = PublicAlert(
            source="ins", title="Alerta INS", url="https://ins.gov.co/alerta",
            snippet="Aviso público", published_date="2026-10-11",
        )
        outcome = review_plate(
            _result(), organism="Escherichia coli", client=client,
            alert_search=_FakeTavilySearch(results=[alert]), alert_sources=["ins"],
        )
        assert outcome.status == "grounded_report"
        assert outcome.report["alert_search_status"] == "available"
        assert outcome.report["public_alerts"][0]["url"] == alert.url

    def test_tavily_failure_is_reported_without_stopping_review(self) -> None:
        client = _configured_client(json.dumps({"explanation": "ok", "evidence_ids": []}))
        outcome = review_plate(
            _result(), organism="Escherichia coli", client=client,
            alert_search=_FakeTavilySearch(fail=True), alert_sources=["ops"],
        )
        assert outcome.status == "grounded_report"
        assert outcome.report["alert_search_status"] == "unavailable"
        assert outcome.report["public_alerts"] == []


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
