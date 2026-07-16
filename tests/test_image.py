from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from bacterioscope.utils.image import load_image, resize_for_inference, save_image


def _bgr_image(h: int = 100, w: int = 150) -> np.ndarray:
    rng = np.random.default_rng(42)
    return (rng.integers(0, 256, (h, w, 3))).astype(np.uint8)


class TestLoadImage:
    def test_loads_valid_png(self, tmp_path: Path) -> None:
        img = _bgr_image(80, 120)
        path = tmp_path / "plate.png"
        cv2.imwrite(str(path), img)
        loaded = load_image(path)
        assert loaded.shape == img.shape
        assert loaded.dtype == np.uint8

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_image(tmp_path / "nonexistent.png")

    def test_raises_on_unsupported_extension(self, tmp_path: Path) -> None:
        path = tmp_path / "file.gif"
        path.write_bytes(b"GIF89a")
        with pytest.raises(ValueError, match="Unsupported image format"):
            load_image(path)

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        img = _bgr_image()
        path = tmp_path / "plate.jpg"
        cv2.imwrite(str(path), img)
        loaded = load_image(str(path))
        assert loaded.ndim == 3


class TestSaveImage:
    def test_writes_png(self, tmp_path: Path) -> None:
        img = _bgr_image()
        out = tmp_path / "out.png"
        save_image(img, out)
        assert out.is_file()
        reloaded = cv2.imread(str(out))
        assert reloaded is not None
        assert reloaded.shape == img.shape

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        img = _bgr_image()
        out = tmp_path / "deep" / "nested" / "plate.png"
        save_image(img, out)
        assert out.is_file()

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        img = _bgr_image()
        out = tmp_path / "plate.png"
        save_image(img, str(out))
        assert out.is_file()


class TestResizeForInference:
    def test_output_is_square(self) -> None:
        img = _bgr_image(300, 500)
        out = resize_for_inference(img, target_size=640)
        assert out.shape == (640, 640, 3)

    def test_square_input_stays_square(self) -> None:
        img = _bgr_image(400, 400)
        out = resize_for_inference(img, target_size=640)
        assert out.shape == (640, 640, 3)

    def test_tall_image(self) -> None:
        img = _bgr_image(800, 200)
        out = resize_for_inference(img, target_size=640)
        assert out.shape == (640, 640, 3)

    def test_default_target_size(self) -> None:
        img = _bgr_image(480, 640)
        out = resize_for_inference(img)
        assert out.shape == (640, 640, 3)

    def test_padding_value_is_grey(self) -> None:
        img = np.zeros((50, 100, 3), dtype=np.uint8)
        out = resize_for_inference(img, target_size=640)
        assert out[0, 0, 0] == 114
