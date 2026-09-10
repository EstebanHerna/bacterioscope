from __future__ import annotations

import cv2
import numpy as np
import pytest

from bacterioscope.detection.detector import DiskResult
from bacterioscope.utils.calibration import (
    calibrate_from_disk_radius_px,
    calibrate_px_per_mm,
    refine_disk_radius_px,
)


def _blank_image(size: int = 400) -> np.ndarray:
    return np.zeros((size, size, 3), dtype=np.uint8)


def _ring_image(size: int = 600, radius: int = 180, thickness: int = 4) -> np.ndarray:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    cv2.circle(image, (size // 2, size // 2), radius, (200, 200, 200), thickness)
    return image


class TestCalibrateFromDiskRadius:
    def test_known_ratio(self) -> None:
        assert calibrate_from_disk_radius_px(30.0) == pytest.approx(10.0)

    def test_custom_disk_diameter(self) -> None:
        assert calibrate_from_disk_radius_px(24.0, disk_diameter_mm=8.0) == pytest.approx(6.0)

    def test_zero_radius_raises(self) -> None:
        with pytest.raises(ValueError, match="disk_radius_px must be positive"):
            calibrate_from_disk_radius_px(0.0)

    def test_negative_radius_raises(self) -> None:
        with pytest.raises(ValueError):
            calibrate_from_disk_radius_px(-5.0)

    def test_zero_diameter_raises(self) -> None:
        with pytest.raises(ValueError, match="disk_diameter_mm must be positive"):
            calibrate_from_disk_radius_px(30.0, disk_diameter_mm=0.0)

    def test_scales_linearly_with_radius(self) -> None:
        low = calibrate_from_disk_radius_px(15.0)
        high = calibrate_from_disk_radius_px(60.0)
        assert high == pytest.approx(low * 4, rel=1e-6)


class TestCalibratePxPerMm:
    def test_returns_two_positive_floats(self) -> None:
        image = _ring_image()
        diameter_px, px_per_mm = calibrate_px_per_mm(image, plate_diameter_mm=90.0)
        assert diameter_px > 0.0
        assert px_per_mm > 0.0

    def test_fallback_when_no_circle_detected(self) -> None:
        image = _blank_image(400)
        diameter_px, px_per_mm = calibrate_px_per_mm(image, plate_diameter_mm=90.0)
        expected = 400 * 0.9
        assert diameter_px == pytest.approx(expected)
        assert px_per_mm == pytest.approx(expected / 90.0)

    def test_larger_plate_diameter_reduces_px_per_mm(self) -> None:
        image = _blank_image(400)
        _, px_90 = calibrate_px_per_mm(image, plate_diameter_mm=90.0)
        _, px_150 = calibrate_px_per_mm(image, plate_diameter_mm=150.0)
        assert px_90 > px_150

    def test_px_per_mm_matches_ratio(self) -> None:
        image = _ring_image()
        diameter_px, px_per_mm = calibrate_px_per_mm(image, plate_diameter_mm=90.0)
        assert px_per_mm == pytest.approx(diameter_px / 90.0, rel=1e-6)

    def test_result_is_in_plausible_range_for_600px_image(self) -> None:
        image = _ring_image(size=600, radius=180)
        _, px_per_mm = calibrate_px_per_mm(image, plate_diameter_mm=90.0)
        assert 1.0 < px_per_mm < 30.0

    def test_square_and_non_square_image_do_not_raise(self) -> None:
        for h, w in ((300, 500), (480, 640)):
            image = np.zeros((h, w, 3), dtype=np.uint8)
            diameter_px, px_per_mm = calibrate_px_per_mm(image)
            assert diameter_px > 0
            assert px_per_mm > 0


def _disk_result(cx: int, cy: int, radius: int) -> DiskResult:
    return DiskResult(
        label="disk_0", center_x=cx, center_y=cy, radius_px=radius,
        confidence=0.9, bbox=(cx - radius, cy - radius, cx + radius, cy + radius),
    )


def _plate_with_disks(size: int, positions: list[tuple[int, int, int]]) -> np.ndarray:
    """Dark background with bright circular disks at the given (cx, cy, radius)."""
    image = np.full((size, size, 3), 60, dtype=np.uint8)
    for cx, cy, r in positions:
        cv2.circle(image, (cx, cy), r, (220, 220, 220), -1)
    return image


class TestRefineDiskRadius:
    def test_recovers_true_radius_independent_of_seed(self) -> None:
        image = _plate_with_disks(400, [(200, 200, 25)])
        # Detector's own seed radius is deliberately wrong (biased low);
        # refinement should recover the true drawn radius regardless.
        disk = _disk_result(200, 200, 15)

        refined = refine_disk_radius_px(image, [disk])

        assert refined == pytest.approx(25.0, abs=2.0)

    def test_median_across_multiple_disks(self) -> None:
        image = _plate_with_disks(500, [(120, 120, 20), (380, 120, 20), (250, 380, 20)])
        disks = [_disk_result(120, 120, 20), _disk_result(380, 120, 20), _disk_result(250, 380, 20)]

        refined = refine_disk_radius_px(image, disks)

        assert refined == pytest.approx(20.0, abs=2.0)

    def test_empty_disks_raises(self) -> None:
        image = _plate_with_disks(300, [])
        with pytest.raises(ValueError, match="disks must be non-empty"):
            refine_disk_radius_px(image, [])

    def test_falls_back_to_seed_radius_when_no_edge_found(self) -> None:
        image = np.full((300, 300, 3), 128, dtype=np.uint8)  # flat, no disk edge anywhere
        disk = _disk_result(150, 150, 18)

        refined = refine_disk_radius_px(image, [disk])

        assert refined > 0.0
