"""Tests for evaluation.plate_report HTML generation."""

from __future__ import annotations

import datetime
from pathlib import Path

import numpy as np

from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.evaluation.plate_report import generate_plate_html, save_plate_report
from bacterioscope.pipeline import AnalysisResult
from bacterioscope.segmentation.watershed import ZoneResult


def _make_result(n: int = 2, include_image: bool = True) -> AnalysisResult:
    disks = [
        DiskResult(
            label=f"disk_{i}", center_x=100 + i * 60, center_y=100,
            radius_px=15, confidence=0.0,
            bbox=(85 + i * 60, 85, 115 + i * 60, 115),
        )
        for i in range(n)
    ]
    zones = [
        ZoneResult(
            disk_label=f"disk_{i}", center_x=100 + i * 60, center_y=100,
            radius_px=40.0, diameter_px=80.0, diameter_mm=26.0,
            area_px=5026.0, circularity=0.95, mask=None,
        )
        for i in range(n)
    ]
    classifications = [
        SusceptibilityResult(
            antibiotic="ciprofloxacin", zone_diameter_mm=26.0,
            category="S", breakpoints={"S": 26.0},
        )
        for _ in range(n)
    ]
    img = np.zeros((300, 400, 3), dtype=np.uint8) if include_image else None
    return AnalysisResult(
        image_path="/tmp/test.jpg",
        plate_diameter_px=300.0,
        px_per_mm=3.33,
        disks=disks,
        zones=zones,
        classifications=classifications,
        annotated_image=img,
        original_image=img,
        flags=[["low_circularity"], []] if n == 2 else [],
    )


class TestGeneratePlateHtml:
    def test_returns_string(self) -> None:
        html = generate_plate_html(_make_result())
        assert isinstance(html, str)

    def test_contains_doctype(self) -> None:
        html = generate_plate_html(_make_result())
        assert "<!DOCTYPE html>" in html

    def test_contains_disclaimer(self) -> None:
        html = generate_plate_html(_make_result())
        assert "decision-support" in html

    def test_contains_antibiotic_name(self) -> None:
        html = generate_plate_html(_make_result())
        assert "ciprofloxacin" in html

    def test_contains_zone_diameter(self) -> None:
        html = generate_plate_html(_make_result())
        assert "26.0" in html

    def test_contains_susceptible_category(self) -> None:
        html = generate_plate_html(_make_result())
        assert ">S<" in html

    def test_contains_flag_badge(self) -> None:
        html = generate_plate_html(_make_result())
        assert "low_circularity" in html

    def test_embeds_image_as_base64(self) -> None:
        html = generate_plate_html(_make_result(include_image=True))
        assert "data:image/png;base64," in html

    def test_no_image_no_base64(self) -> None:
        result = _make_result(include_image=False)
        html = generate_plate_html(result)
        assert "data:image/png;base64," not in html

    def test_custom_timestamp_appears(self) -> None:
        ts = datetime.datetime(2026, 1, 15, 10, 30, tzinfo=datetime.timezone.utc)
        html = generate_plate_html(_make_result(), analysis_time=ts)
        assert "2026-01-15" in html

    def test_calibration_info_present(self) -> None:
        html = generate_plate_html(_make_result())
        assert "px/mm" in html


class TestSavePlateReport:
    def test_creates_html_file(self, tmp_path: Path) -> None:
        out = tmp_path / "report.html"
        save_plate_report(_make_result(), out)
        assert out.exists()
        assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "dir" / "report.html"
        save_plate_report(_make_result(), out)
        assert out.exists()
