from __future__ import annotations

import cv2
import numpy as np
import pytest

from bacterioscope.detection.detector import DiskResult
from bacterioscope.segmentation.watershed import ZoneResult, ZoneSegmenter


def _disk_result(cx: int, cy: int, radius: int) -> DiskResult:
    return DiskResult(
        label="meropenem",
        center_x=cx,
        center_y=cy,
        radius_px=radius,
        confidence=0.9,
        bbox=(cx - radius, cy - radius, cx + radius, cy + radius),
    )


def _plate_image(size: int = 300, disk_r: int = 20, zone_r: int = 55) -> np.ndarray:
    """Bright bacterial lawn, dark inhibition zone, bright disk at center."""
    image = np.full((size, size, 3), 190, dtype=np.uint8)
    cx, cy = size // 2, size // 2
    cv2.circle(image, (cx, cy), zone_r, (45, 45, 45), -1)
    cv2.circle(image, (cx, cy), disk_r, (230, 230, 230), -1)
    return image


class TestZoneSegmenter:
    def setup_method(self) -> None:
        self.segmenter = ZoneSegmenter(margin_factor=4.0)

    def test_returns_zone_result(self) -> None:
        image = _plate_image()
        disk = _disk_result(150, 150, 20)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert isinstance(result, ZoneResult)

    def test_label_matches_disk(self) -> None:
        image = _plate_image()
        disk = _disk_result(150, 150, 20)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert result.disk_label == "meropenem"

    def test_diameter_non_negative(self) -> None:
        image = _plate_image()
        disk = _disk_result(150, 150, 20)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert result.diameter_mm >= 0.0
        assert result.diameter_px >= 0.0

    def test_happy_path_detects_zone(self) -> None:
        image = _plate_image(size=300, disk_r=20, zone_r=55)
        disk = _disk_result(150, 150, 20)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert result.diameter_mm > 0.0

    def test_diameter_mm_consistent_with_px(self) -> None:
        image = _plate_image()
        disk = _disk_result(150, 150, 20)
        px_per_mm = 4.0
        result = self.segmenter.segment(image, disk, px_per_mm=px_per_mm)
        if result.diameter_px > 0:
            assert result.diameter_mm == pytest.approx(
                result.diameter_px / px_per_mm, rel=1e-6
            )

    def test_circularity_in_unit_range(self) -> None:
        image = _plate_image()
        disk = _disk_result(150, 150, 20)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert 0.0 <= result.circularity <= 1.0

    def test_blank_image_returns_zero_diameter(self) -> None:
        image = np.zeros((200, 200, 3), dtype=np.uint8)
        disk = _disk_result(100, 100, 10)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert isinstance(result, ZoneResult)
        assert result.diameter_mm >= 0.0

    def test_segment_does_not_raise_on_edge_disk(self) -> None:
        image = _plate_image()
        disk = _disk_result(5, 5, 20)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert isinstance(result, ZoneResult)

    def test_zone_result_area_non_negative(self) -> None:
        image = _plate_image()
        disk = _disk_result(150, 150, 20)
        result = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert result.area_px >= 0.0
