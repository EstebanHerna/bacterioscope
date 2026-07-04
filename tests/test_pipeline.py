from __future__ import annotations

import stat as stat_module
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

from bacterioscope.pipeline import BacterioScopePipeline

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
