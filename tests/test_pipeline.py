from __future__ import annotations

import stat as stat_module
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline
from bacterioscope.segmentation.watershed import ZoneResult

_MAX_IMAGE_BYTES = 50 * 1024 * 1024  # mirrors pipeline constant


class TestPipelineInputValidation:
    def setup_method(self) -> None:
        self.pipeline = BacterioScopePipeline()

    def test_nonexistent_file_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            self.pipeline.analyze("does/not/exist/image.jpg")

    def test_unsupported_extension_raises_value_error(self, tmp_path: Path) -> None:
        bad = tmp_path / "plate.gif"
        bad.write_bytes(b"not an image")
        with pytest.raises(ValueError, match="Unsupported image format"):
            self.pipeline.analyze(bad)

    def test_txt_extension_rejected(self, tmp_path: Path) -> None:
        bad = tmp_path / "data.txt"
        bad.write_bytes(b"not an image")
        with pytest.raises(ValueError, match="Unsupported image format"):
            self.pipeline.analyze(bad)

    def test_file_exceeding_size_limit_raises(self, tmp_path: Path) -> None:
        oversized = tmp_path / "huge.jpg"
        oversized.write_bytes(b"x")
        mock_stat = MagicMock()
        mock_stat.st_size = _MAX_IMAGE_BYTES + 1
        mock_stat.st_mode = stat_module.S_IFREG | 0o644  # is_file() needs a valid mode
        with patch.object(Path, "stat", return_value=mock_stat):
            with pytest.raises(ValueError, match="50 MB"):
                self.pipeline.analyze(oversized)

    def test_corrupted_image_raises_value_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.png"
        corrupt.write_bytes(b"\x00\x01\x02\x03 not valid image data")
        with pytest.raises(ValueError, match="Could not decode"):
            self.pipeline.analyze(corrupt)

    def test_allowed_extensions_do_not_raise_on_valid_image(self, tmp_path: Path) -> None:
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        for ext in (".jpg", ".jpeg", ".png", ".bmp"):
            path = tmp_path / f"plate{ext}"
            cv2.imwrite(str(path), image)
            result = self.pipeline.analyze(path)
            assert result.px_per_mm > 0

    def test_watermarked_image_rejected(self, tmp_path: Path) -> None:
        image = np.zeros((300, 300, 3), dtype=np.uint8)
        image[0:18, 0:18] = (255, 0, 255)  # matches visualization.WATERMARK_COLOR
        path = tmp_path / "already_annotated.png"
        cv2.imwrite(str(path), image)
        with pytest.raises(ValueError, match="watermark"):
            self.pipeline.analyze(path)


class TestReclassifyWithLabels:
    def test_preserves_analysis_traceability_metadata(self) -> None:
        pipeline = BacterioScopePipeline()
        disk = DiskResult(
            label="disk_0", center_x=10, center_y=10, radius_px=3.0,
            confidence=1.0, bbox=(7, 7, 13, 13),
        )
        zone = ZoneResult(
            disk_label="disk_0", center_x=10, center_y=10, radius_px=5.0,
            diameter_px=10.0, diameter_mm=8.0, area_px=78.0,
            circularity=0.9, mask=None,
        )
        original_classification = SusceptibilityResult(
            antibiotic="disk_0", zone_diameter_mm=8.0, category="UNKNOWN", breakpoints={}
        )
        updated_classification = SusceptibilityResult(
            antibiotic="ciprofloxacin", zone_diameter_mm=8.0, category="R",
            breakpoints={"S": 21.0, "R": 15.0},
        )
        analysis = AnalysisResult(
            image_path="synthetic.png", plate_diameter_px=500.0, px_per_mm=5.5,
            disks=[disk], zones=[zone], classifications=[original_classification],
            flags=[["low_circularity"]], plate_center=(20, 20),
            analysis_id="analysis-123", software_version="0.1.0", commit_hash="abc123",
            breakpoint_table_version="CLSI M100-Ed33 2023", image_sha256="a" * 64,
            timings_ms={"total_ms": 12.3}, canonical_scale_factor=0.5,
            disk_calibration_ratio=1.02,
        )
        with patch.object(pipeline.classifier, "classify", return_value=updated_classification):
            updated = pipeline.reclassify_with_labels(analysis, ["ciprofloxacin"])

        assert updated.classifications == [updated_classification]
        assert updated.analysis_id == analysis.analysis_id
        assert updated.breakpoint_table_version == analysis.breakpoint_table_version
        assert updated.image_sha256 == analysis.image_sha256
        assert updated.timings_ms == analysis.timings_ms
        assert updated.canonical_scale_factor == analysis.canonical_scale_factor
        assert updated.disk_calibration_ratio == analysis.disk_calibration_ratio
        assert updated.flags == analysis.flags

    def test_rejects_mismatched_panel_assignments(self) -> None:
        pipeline = BacterioScopePipeline()
        analysis = AnalysisResult(
            image_path="synthetic.png", plate_diameter_px=100.0, px_per_mm=1.0,
            disks=[DiskResult(
                label="disk_0", center_x=10, center_y=10, radius_px=3.0,
                confidence=1.0, bbox=(7, 7, 13, 13),
            )],
            zones=[],
        )
        with pytest.raises(ValueError, match="same length"):
            pipeline.reclassify_with_labels(analysis, [])
