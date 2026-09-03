from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from bacterioscope.detection.detector import DiskDetector, DiskResult
from bacterioscope.detection.label_map import ROBOFLOW_TO_CLSI


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


class TestHoughStableParam2Sweep:
    """Regression: a single fixed param2 cannot serve both real photos (need
    a strict threshold to reject agar texture as false circles) and synthetic
    plates (softer, blurred disk edges drop below that threshold). See
    detector.py::_hough_stable_circles.
    """
    def setup_method(self) -> None:
        self.detector = _make_detector()

    def test_committed_synthetic_plates_detect_all_six_disks(self) -> None:
        examples_dir = Path(__file__).parent.parent / "examples" / "synthetic"
        px_per_mm = 540 / (90 * 1.14)
        for name in (
            "plate_pan_susceptible", "plate_mixed_sir", "plate_mdr_organism",
            "plate_large_zones", "plate_esbl_like",
        ):
            path = examples_dir / f"{name}.png"
            image = cv2.imread(str(path))
            assert image is not None, f"Missing fixture: {path}"
            disks = self.detector.detect(image, px_per_mm=px_per_mm)
            assert len(disks) == 6, f"{name}: expected 6 disks, got {len(disks)}"

    def test_calibrated_path_still_finds_disks_on_synthetic_helper(self) -> None:
        plate = _make_synthetic_plate()
        px_per_mm = 540 / (90 * 1.14)
        disks = self.detector.detect(plate, px_per_mm=px_per_mm)
        assert len(disks) == 6


class TestLabelMap:
    def test_known_classes_map_to_clsi_keys(self) -> None:
        assert ROBOFLOW_TO_CLSI["CIP 10"] == "ciprofloxacin"
        assert ROBOFLOW_TO_CLSI["MEM 10"] == "meropenem"
        assert ROBOFLOW_TO_CLSI["GEN 10"] == "gentamicin"

    def test_gm_and_gen_both_map_to_gentamicin(self) -> None:
        assert ROBOFLOW_TO_CLSI["GM 10"] == "gentamicin"
        assert ROBOFLOW_TO_CLSI["GEN 10"] == "gentamicin"

    def test_ctx_maps_to_ceftriaxone(self) -> None:
        assert ROBOFLOW_TO_CLSI["CTX 30"] == "ceftriaxone"
        assert ROBOFLOW_TO_CLSI["CRO 30"] == "ceftriaxone"

    def test_carbapenems_mapped(self) -> None:
        assert ROBOFLOW_TO_CLSI["IPM 10"] == "imipenem"
        assert ROBOFLOW_TO_CLSI["MEM 10"] == "meropenem"

    def test_all_values_are_strings(self) -> None:
        assert all(isinstance(v, str) for v in ROBOFLOW_TO_CLSI.values())

    def test_no_empty_keys_or_values(self) -> None:
        assert all(k and v for k, v in ROBOFLOW_TO_CLSI.items())

    def test_gram_positive_drug_not_in_map(self) -> None:
        assert "VA 30" not in ROBOFLOW_TO_CLSI

    def test_missing_key_returns_raw_label(self) -> None:
        assert ROBOFLOW_TO_CLSI.get("VA 30", "VA 30") == "VA 30"


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
