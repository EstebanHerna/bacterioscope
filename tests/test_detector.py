from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from bacterioscope.detection.detector import DiskDetector, DiskResult


def _make_detector() -> DiskDetector:
    return DiskDetector(weights=Path("nonexistent_weights.pt"), confidence=0.5)


def _blank_image(size: int = 300) -> np.ndarray:
    return np.zeros((size, size, 3), dtype=np.uint8)


def _disk_image(size: int = 400) -> np.ndarray:
    image = np.full((size, size, 3), 30, dtype=np.uint8)
    for cx, cy in ((100, 100), (300, 100), (200, 300)):
        cv2.circle(image, (cx, cy), 15, (220, 220, 220), -1)
    return image


class TestDiskDetectorHoughMode:
    def setup_method(self) -> None:
        self.detector = _make_detector()

    def test_no_weights_uses_hough(self) -> None:
        self.detector._load_model()
        assert self.detector._model is None

    def test_detect_returns_list(self) -> None:
        result = self.detector.detect(_disk_image())
        assert isinstance(result, list)

    def test_blank_image_returns_empty_list(self) -> None:
        result = self.detector.detect(_blank_image())
        assert result == []

    def test_each_result_is_disk_result_instance(self) -> None:
        for disk in self.detector.detect(_disk_image()):
            assert isinstance(disk, DiskResult)

    def test_disk_center_within_image_bounds(self) -> None:
        image = _disk_image(400)
        for disk in self.detector.detect(image):
            assert 0 <= disk.center_x < image.shape[1]
            assert 0 <= disk.center_y < image.shape[0]

    def test_disk_radius_positive(self) -> None:
        for disk in self.detector.detect(_disk_image()):
            assert disk.radius_px > 0

    def test_disk_label_format(self) -> None:
        for disk in self.detector.detect(_disk_image()):
            assert disk.label.startswith("disk_")

    def test_bbox_is_four_ints(self) -> None:
        for disk in self.detector.detect(_disk_image()):
            assert len(disk.bbox) == 4
            assert all(isinstance(v, int) for v in disk.bbox)

    def test_confidence_zero_in_hough_mode(self) -> None:
        for disk in self.detector.detect(_disk_image()):
            assert disk.confidence == 0.0

    def test_detect_is_deterministic(self) -> None:
        image = _disk_image()
        result_a = [(d.center_x, d.center_y) for d in self.detector.detect(image)]
        result_b = [(d.center_x, d.center_y) for d in self.detector.detect(image)]
        assert result_a == result_b

    def test_detects_six_disks_on_synthetic_plate(self) -> None:
        """Regression: param1=50/param2=20 must detect all 6 disks on the demo plate."""
        plate = _make_synthetic_plate()
        disks = self.detector.detect(plate)
        assert len(disks) == 6, (
            f"Expected 6 disks on synthetic plate, got {len(disks)}. "
            "HoughCircles param1/param2 may need re-tuning."
        )

    def test_detected_disk_radii_in_expected_range(self) -> None:
        plate = _make_synthetic_plate()
        for disk in self.detector.detect(plate):
            assert 10 <= disk.radius_px <= 40


def _make_synthetic_plate(size: int = 540) -> np.ndarray:
    center = (size // 2, size // 2)
    plate_r = 252
    disk_r = 14
    angles = [90, 30, 330, 270, 210, 150]
    positions = [
        (center[0] + int(170 * np.cos(np.radians(a))),
         center[1] - int(170 * np.sin(np.radians(a))))
        for a in angles
    ]
    img = np.full((size, size, 3), [38, 38, 38], dtype=np.uint8)
    agar = np.full((size, size, 3), [136, 165, 186], dtype=np.uint8)
    mask = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(mask, center, plate_r, 255, -1)
    img[mask > 0] = agar[mask > 0]
    for cx, cy in positions:
        cv2.circle(img, (cx, cy), disk_r, (232, 232, 225), -1)
    return img
