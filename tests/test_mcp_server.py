"""Tests for the MCP server (mcp_server.py), called in process through FastMCP."""

from __future__ import annotations

import json
from typing import Any

import anyio
import pytest

pytest.importorskip("mcp")

from mcp.server.fastmcp.exceptions import ToolError  # noqa: E402

from bacterioscope import plate_session  # noqa: E402
from bacterioscope.mcp_server import mcp  # noqa: E402

_SAMPLE = "plate_mixed_sir"


def _call(name: str, params: dict[str, Any] | None = None) -> str:
    async def run() -> str:
        result = await mcp.call_tool(name, {"params": params} if params is not None else {})
        content = result[0] if isinstance(result, tuple) else result
        return str(content[0].text)

    return anyio.run(run)


def _json(name: str, params: dict[str, Any]) -> Any:
    return json.loads(_call(name, {**params, "response_format": "json"}))


@pytest.fixture(autouse=True)
def _no_live_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEBIUS_API_KEY", "")
    monkeypatch.setattr(plate_session, "_models", None)


@pytest.fixture(scope="module")
def plate() -> dict[str, Any]:
    return dict(_json("bacterioscope_analyze_plate", {"sample_id": _SAMPLE}))


class TestCatalog:
    def test_every_tool_is_prefixed_and_annotated(self) -> None:
        tools = anyio.run(mcp.list_tools)
        assert len(tools) == 7
        for tool in tools:
            assert tool.name.startswith("bacterioscope_")
            assert tool.annotations is not None
            assert tool.annotations.destructiveHint is False

    def test_lookups_are_read_only(self) -> None:
        tools = {t.name: t for t in anyio.run(mcp.list_tools)}
        for name in ("bacterioscope_classify_zone", "bacterioscope_get_breakpoints",
                     "bacterioscope_list_samples", "bacterioscope_list_panels"):
            assert tools[name].annotations.readOnlyHint is True

    def test_samples_and_panels(self) -> None:
        samples = {s["sample_id"]: s for s in json.loads(_call("bacterioscope_list_samples"))}
        assert samples[_SAMPLE] == {"sample_id": _SAMPLE, "synthetic": True, "disks": 6}
        panels = {p["panel"]: p for p in json.loads(_call("bacterioscope_list_panels"))}
        assert len(panels["enterobacteria_clsi_6"]["antibiotics"]) == 6


class TestBreakpoints:
    def test_classify_by_code_with_whole_mm_rounding(self) -> None:
        body = json.loads(_call("bacterioscope_classify_zone",
                                {"antibiotic": "MEM", "diameter_mm": 21.6}))
        assert body["antibiotic"] == "meropenem"
        assert body["whole_mm"] == 22
        assert body["category"] == "I"
        assert body["near_breakpoint"] is True

    def test_sdd_category(self) -> None:
        body = json.loads(_call("bacterioscope_classify_zone",
                                {"antibiotic": "cefepime", "diameter_mm": 20}))
        assert body["category"] == "SDD"

    def test_unknown_antibiotic_points_to_the_table(self) -> None:
        with pytest.raises(ToolError, match="bacterioscope_get_breakpoints"):
            _call("bacterioscope_classify_zone", {"antibiotic": "vancomycin", "diameter_mm": 15})

    def test_full_table(self) -> None:
        body = _json("bacterioscope_get_breakpoints", {})
        assert len(body["breakpoints"]) == 15


class TestAnalyze:
    def test_sample_layout_is_assigned_in_clockwise_positions(self, plate: dict[str, Any]) -> None:
        assert plate["synthetic_sample"] is True
        assert [d["position"] for d in plate["disks"]] == [1, 2, 3, 4, 5, 6]
        assert all(d["antibiotic"] for d in plate["disks"])
        assert {d["category"] for d in plate["disks"]} <= {"S", "I", "SDD", "R"}

    def test_markdown_carries_the_disclaimer(self) -> None:
        text = _call("bacterioscope_analyze_plate", {"sample_id": _SAMPLE})
        assert "| Pos | Antibiotic |" in text
        assert "not a medical device" in text

    def test_wrong_antibiotic_count_is_explained(self) -> None:
        with pytest.raises(ToolError, match="6 disks were detected"):
            _call("bacterioscope_analyze_plate", {"sample_id": _SAMPLE, "antibiotics": ["CIP"]})

    def test_panel_assignment(self) -> None:
        body = _json("bacterioscope_analyze_plate",
                     {"sample_id": _SAMPLE, "panel": "enterobacteria_clsi_6"})
        assert all(d["antibiotic"] for d in body["disks"])

    def test_missing_image_file(self, tmp_path: Any) -> None:
        with pytest.raises(ToolError, match="No file"):
            _call("bacterioscope_analyze_plate", {"image_path": str(tmp_path / "plate.jpg")})

    def test_rejects_non_image_paths(self) -> None:
        with pytest.raises(ToolError, match="JPEG, PNG"):
            _call("bacterioscope_analyze_plate", {"image_path": "pyproject.toml"})

    def test_needs_exactly_one_source(self) -> None:
        with pytest.raises(ToolError):
            _call("bacterioscope_analyze_plate",
                  {"sample_id": _SAMPLE, "image_path": "examples/real/real_plate_box4.jpg"})


class TestUpdateAndReview:
    def test_correction_blocks_review_until_cleared(self, plate: dict[str, Any]) -> None:
        analysis = plate["analysis_id"]
        body = _json("bacterioscope_update_plate",
                     {"analysis_id": analysis, "corrections": {"1": 35.0}})
        first = body["disks"][0]
        assert first["corrected"] is True
        assert first["diameter_mm"] == 35.0
        assert body["review_blocked"] is True
        with pytest.raises(ToolError, match="Manual corrections"):
            _call("bacterioscope_review_plate", {"analysis_id": analysis})
        cleared = _json("bacterioscope_update_plate",
                        {"analysis_id": analysis, "clear_corrections": True})
        assert cleared["review_blocked"] is False

    def test_assignment_by_code(self, plate: dict[str, Any]) -> None:
        body = _json("bacterioscope_update_plate",
                     {"analysis_id": plate["analysis_id"], "assignments": {"2": "AK"}})
        assert body["disks"][1]["antibiotic"] == "amikacin"

    def test_unknown_position(self, plate: dict[str, Any]) -> None:
        with pytest.raises(ToolError, match="Positions \\[9\\]"):
            _call("bacterioscope_update_plate",
                  {"analysis_id": plate["analysis_id"], "assignments": {"9": "CIP"}})

    def test_review_without_provider_is_a_complete_fallback(self, plate: dict[str, Any]) -> None:
        body = _json("bacterioscope_review_plate", {"analysis_id": plate["analysis_id"]})
        assert body["status"] == "fallback"
        assert body["fallback_reason"] == "token_factory_unavailable"
        assert len(body["report"]["measurement"]["observations"]) == 6

    def test_expired_analysis(self) -> None:
        with pytest.raises(ToolError, match="analyze the plate again"):
            _call("bacterioscope_update_plate", {"analysis_id": "00000000-missing"})
