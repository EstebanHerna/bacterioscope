"""Image I/O and preprocessing utilities.

Centralises safe image loading, saving, and resizing so that every part of
the pipeline uses the same validation logic:

- ``pipeline.py`` (single-image analysis)
- ``scripts/evaluate.py`` (batch evaluation against ground-truth CSV)
- ``scripts/generate_demo.py`` (synthetic demo image generation)
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

_ALLOWED_SUFFIXES: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
)
_MAX_IMAGE_BYTES: int = 50 * 1024 * 1024  # 50 MB


def load_image(path: str | Path) -> NDArray[np.uint8]:
    """Load an image from disk and return a BGR NumPy array.

    Args:
        path: Path to the image file. Supported formats: JPEG, PNG, BMP, TIFF.

    Returns:
        BGR image array with dtype uint8.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the format is unsupported, the file exceeds 50 MB, or
            OpenCV cannot decode the image.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    if path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise ValueError(f"Unsupported image format: {path.suffix!r}")
    if path.stat().st_size > _MAX_IMAGE_BYTES:
        raise ValueError(f"Image exceeds 50 MB size limit: {path}")
    image: NDArray[np.uint8] | None = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    return image


def save_image(image: NDArray[np.uint8], path: str | Path) -> None:
    """Write a BGR image array to disk, creating parent directories if needed.

    Args:
        image: BGR image array with dtype uint8.
        path: Destination file path. The format is inferred from the suffix.

    Raises:
        ValueError: If OpenCV cannot encode the image to the requested format.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(path), image)
    if not success:
        raise ValueError(f"Could not write image to {path}")


def resize_for_inference(
    image: NDArray[np.uint8],
    target_size: int = 640,
) -> NDArray[np.uint8]:
    """Resize an image to a square via letterboxing, preserving aspect ratio.

    YOLOv8 expects a square input (default 640x640). Stretching the image
    would distort the circular disk shapes and degrade detection accuracy.
    This function scales the image to fit within ``target_size`` and pads
    the remaining area with neutral grey (value 114, the Ultralytics default).

    Args:
        image: BGR source image.
        target_size: Side length of the output square in pixels. Must match
            the ``imgsz`` used during training (default 640).

    Returns:
        Square BGR image of shape ``(target_size, target_size, 3)`` with
        grey letterbox padding on the shorter axis.
    """
    h, w = image.shape[:2]
    scale = target_size / max(h, w)
    new_h = int(h * scale)
    new_w = int(w * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((target_size, target_size, 3), 114, dtype=np.uint8)
    pad_y = (target_size - new_h) // 2
    pad_x = (target_size - new_w) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return canvas
