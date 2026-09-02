"""Tests for visualization.draw_results() with real contours and flags."""

from __future__ import annotations

import cv2
import numpy as np

from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.segmentation.watershed import ZoneResult
from bacterioscope.utils.visualization import draw_results, has_watermark


def _make_disk(cx: int = 100, cy: int = 100, r: int = 15) -> DiskResult:
    return DiskResult(
        label="ciprofloxacin", center_x=cx, center_y=cy, radius_px=r,
        confidence=1.0, bbox=(cx - r, cy - r, cx + r, cy + r),
    )


def _make_zone(cx: int = 100, cy: int = 100, r: float = 40.0,
               mm: float = 26.0, mask: np.ndarray | None = None) -> ZoneResult:
    return ZoneResult(
        disk_label="ciprofloxacin", center_x=cx, center_y=cy,
        radius_px=r, diameter_px=r * 2, diameter_mm=mm,
        area_px=np.pi * r ** 2, circularity=0.95, mask=mask,
    )


def _make_cls(cat: str = "S", mm: float = 26.0) -> SusceptibilityResult:
    return SusceptibilityResult(
        antibiotic="ciprofloxacin", zone_diameter_mm=mm,
        category=cat, breakpoints={"S": 26.0, "R": 21.0},
    )


class TestDrawResultsBasic:
    def test_returns_same_array(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        out = draw_results(img, [_make_disk()], [_make_zone()], [_make_cls()])
        assert out is img

    def test_no_disks_returns_unchanged_shape(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        out = draw_results(img, [], [], [])
        assert out.shape == (300, 300, 3)

    def test_modifies_image_when_disk_present(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        original = img.copy()
        draw_results(img, [_make_disk()], [_make_zone()], [_make_cls()])
        assert not np.array_equal(img, original)

    def test_stroke_color_override_applied(self) -> None:
        img_default = np.zeros((300, 300, 3), dtype=np.uint8)
        img_override = np.zeros((300, 300, 3), dtype=np.uint8)
        draw_results(img_default, [_make_disk()], [_make_zone()], [_make_cls()])
        draw_results(img_override, [_make_disk()], [_make_zone()], [_make_cls()],
                     stroke_color=(255, 255, 255))
        assert not np.array_equal(img_default, img_override)


class TestDrawResultsContour:
    def test_draws_contour_from_mask(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        mask = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(mask, (100, 100), 40, 255, -1)
        zone = _make_zone(mask=mask)
        draw_results(img, [_make_disk()], [zone], [_make_cls()])
        assert img.any()

    def test_fallback_circle_when_no_mask(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        zone = _make_zone(mask=None)
        draw_results(img, [_make_disk()], [zone], [_make_cls()])
        assert img.any()

    def test_zero_radius_zone_does_not_crash(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        zone = _make_zone(r=0.0, mm=0.0)
        draw_results(img, [_make_disk()], [zone], [_make_cls()])


class TestDrawResultsFlags:
    def test_empty_flags_no_crash(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        draw_results(img, [_make_disk()], [_make_zone()], [_make_cls()], flags=[[]])

    def test_flagged_disk_draws_extra_ring(self) -> None:
        img_flagged = np.zeros((300, 300, 3), dtype=np.uint8)
        img_clean = np.zeros((300, 300, 3), dtype=np.uint8)
        draw_results(img_flagged, [_make_disk()], [_make_zone()], [_make_cls()],
                     flags=[["low_circularity"]])
        draw_results(img_clean, [_make_disk()], [_make_zone()], [_make_cls()],
                     flags=[[]])
        assert not np.array_equal(img_flagged, img_clean)

    def test_flags_none_behaves_like_empty(self) -> None:
        img_none = np.zeros((300, 300, 3), dtype=np.uint8)
        img_empty = np.zeros((300, 300, 3), dtype=np.uint8)
        draw_results(img_none, [_make_disk()], [_make_zone()], [_make_cls()], flags=None)
        draw_results(img_empty, [_make_disk()], [_make_zone()], [_make_cls()], flags=[[]])
        assert np.array_equal(img_none, img_empty)


class TestWatermark:
    def test_draw_results_stamps_watermark(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        draw_results(img, [_make_disk()], [_make_zone()], [_make_cls()])
        assert has_watermark(img)

    def test_fresh_image_has_no_watermark(self) -> None:
        img = np.full((300, 300, 3), 148, dtype=np.uint8)
        assert not has_watermark(img)

    def test_watermark_survives_jpeg_recompression(self) -> None:
        img = np.zeros((300, 300, 3), dtype=np.uint8)
        draw_results(img, [_make_disk()], [_make_zone()], [_make_cls()])
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        assert ok
        recompressed = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        assert has_watermark(recompressed)

    def test_tiny_image_does_not_crash(self) -> None:
        img = np.zeros((3, 3, 3), dtype=np.uint8)
        assert has_watermark(img) in (True, False)
