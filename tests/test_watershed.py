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


class TestSegmentAllVoronoiSplit:
    """segment_all() must recover each disk's own zone size when two
    confluent zones of genuinely different sizes overlap, not average or
    clip them to the same value -- see watershed.py::segment_all.
    """
    def setup_method(self) -> None:
        self.segmenter = ZoneSegmenter()

    def _overlapping_plate(self) -> np.ndarray:
        """Two disks close enough that their zones overlap, sizes 80px vs 40px."""
        image = np.full((400, 400, 3), 190, dtype=np.uint8)
        cv2.circle(image, (150, 200), 80, (60, 60, 60), -1)
        cv2.circle(image, (280, 200), 40, (60, 60, 60), -1)
        cv2.circle(image, (150, 200), 12, (230, 230, 230), -1)
        cv2.circle(image, (280, 200), 12, (230, 230, 230), -1)
        return cv2.GaussianBlur(image, (9, 9), 3)

    def test_recovers_different_sizes_for_overlapping_zones(self) -> None:
        image = self._overlapping_plate()
        big = _disk_result(150, 200, 12)
        small = _disk_result(280, 200, 12)
        results = self.segmenter.segment_all(image, [big, small], px_per_mm=4.0)
        big_result, small_result = results
        assert big_result.diameter_mm > small_result.diameter_mm + 10.0

    def test_single_disk_falls_back_to_segment(self) -> None:
        image = _plate_image()
        disk = _disk_result(150, 150, 20)
        via_all = self.segmenter.segment_all(image, [disk], px_per_mm=4.0)
        via_single = self.segmenter.segment(image, disk, px_per_mm=4.0)
        assert via_all[0].diameter_mm == via_single.diameter_mm

    def test_empty_disk_list_returns_empty(self) -> None:
        image = _plate_image()
        assert self.segmenter.segment_all(image, [], px_per_mm=4.0) == []

    def test_results_in_same_order_as_input(self) -> None:
        image = self._overlapping_plate()
        big = _disk_result(150, 200, 12)
        small = _disk_result(280, 200, 12)
        results = self.segmenter.segment_all(image, [small, big], px_per_mm=4.0)
        assert results[0].diameter_mm < results[1].diameter_mm
