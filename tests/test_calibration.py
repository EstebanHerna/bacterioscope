from __future__ import annotations

import cv2
import numpy as np
import pytest

from bacterioscope.utils.calibration import calibrate_px_per_mm


def _blank_image(size: int = 400) -> np.ndarray:
    return np.zeros((size, size, 3), dtype=np.uint8)


def _ring_image(size: int = 600, radius: int = 180, thickness: int = 4) -> np.ndarray:
    image = np.zeros((size, size, 3), dtype=np.uint8)
    cv2.circle(image, (size // 2, size // 2), radius, (200, 200, 200), thickness)
    return image


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
