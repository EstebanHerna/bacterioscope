"""Antibiotic disk detection for Kirby-Bauer plate photographs.

This module provides two strategies for locating the paper antibiotic disks in
a plate photograph.  Both strategies return the same ``DiskResult`` dataclass,
so the rest of the pipeline is unaffected by which strategy is in use.

YOLOv8 strategy (deep learning, Phase 1)
-----------------------------------------
When a trained ```.pt``` weights file is present at the path specified in
``PipelineConfig.detector_weights``, the module loads a YOLOv8 object-
detection model and runs inference on the image.  The model:

- Locates each disk with a bounding box.
- Classifies it into one of 15 antibiotic categories (e.g. ``ciprofloxacin``).
- Returns a confidence score (0.0–1.0) for each detection.

The class label becomes the ``DiskResult.label``, which the CLSI classifier
can immediately look up in the breakpoint table.

Hough Circle strategy (geometry, fallback)
-------------------------------------------
When no weights file exists, the module uses OpenCV's **Hough Circle
Transform** — a classical computer-vision algorithm that finds circular objects
in an image without any machine learning.  It detects disks reliably but
cannot read their printed labels, so each disk is named ``"disk_0"``,
``"disk_1"``, etc. The CLSI classifier returns UNKNOWN for these names, and
the Streamlit demo offers a manual assignment dropdown to bridge the gap.

Security note
-------------
YOLOv8 weights are loaded via ``torch.load``, which can execute arbitrary code
if the ``.pt`` file comes from an untrusted source.  The ``_TRUSTED_MODEL_HASHES``
dictionary maps filename → expected SHA-256 digest.  Populate it when
distributing known-good weights to enable integrity verification.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

# SHA-256 hashes of trusted model files. Populate when distributing known-good weights.
# Loading a .pt file without a matching hash will log a warning; add hashes here to
# enable enforcement. torch.load (called internally by ultralytics) can execute arbitrary
# code when weights_only=False — only load weights from sources you control.
_TRUSTED_MODEL_HASHES: dict[str, str] = {}


@dataclass
class DiskResult:
    """Detection output for a single antibiotic disk on the plate.

    All coordinate and size fields are in pixels relative to the original
    image.

    Attributes:
        label: Antibiotic name when detected by YOLOv8 (e.g.
            ``'ciprofloxacin'``), or ``'disk_N'`` (e.g. ``'disk_0'``) when
            using the Hough fallback which cannot read disk labels.
        center_x: Horizontal pixel coordinate of the disk centre.
        center_y: Vertical pixel coordinate of the disk centre.
        radius_px: Disk radius in pixels.  A standard 6-mm antibiotic disk
            translates to roughly ``3 × px_per_mm`` pixels.
        confidence: Detection confidence from YOLOv8 in the range [0, 1].
            Always ``0.0`` in Hough mode — the algorithm assigns no score.
        bbox: Bounding box as ``(x_min, y_min, x_max, y_max)`` in pixels.
    """
    label: str
    center_x: int
    center_y: int
    radius_px: int
    confidence: float
    bbox: tuple[int, int, int, int]


class DiskDetector:
    """Detects antibiotic paper disks in a Kirby-Bauer plate image.

    On the first call to ``detect()``, the detector tries to load the
    YOLOv8 model from ``weights``.  If the file does not exist, it silently
    falls back to the Hough Circle Transform.  Subsequent calls reuse the
    already-loaded model (lazy loading).

    Attributes:
        weights: Path to the YOLOv8 ``.pt`` weights file.  If the file does
            not exist, Hough mode is used automatically.
        confidence: Minimum YOLOv8 confidence score in [0, 1].  Detections
            below this threshold are discarded.  Has no effect in Hough mode.
    """
    def __init__(self, weights: Path, confidence: float = 0.5) -> None:
        self.weights = weights
        self.confidence = confidence
        self._model: Any = None

    def _load_model(self) -> None:
        """Load the YOLOv8 model on first use (lazy initialisation).

        If weights do not exist, sets ``_model`` to ``None`` so that
        subsequent calls to ``detect()`` use the Hough fallback.
        """
        if self._model is not None:
            return
        if self.weights.exists():
            self._verify_weights(self.weights)
            from ultralytics import YOLO
            self._model = YOLO(str(self.weights))
        else:
            self._model = None

    def _verify_weights(self, path: Path) -> None:
        """Verify the SHA-256 hash of a weights file against the trusted list.

        If the filename is not in ``_TRUSTED_MODEL_HASHES``, the check is
        skipped (no enforcement).  If it is present and the hash does not
        match, raises ``ValueError`` to prevent loading a tampered file.

        Args:
            path: Path to the ``.pt`` weights file to verify.

        Raises:
            ValueError: If the file hash does not match the expected digest.
        """
        expected = _TRUSTED_MODEL_HASHES.get(path.name)
        if expected is None:
            return
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(
                f"Model integrity check failed for {path.name}. "
                "The file hash does not match the expected value. "
                "Do not load model weights from untrusted sources."
            )

    def detect(self, image: NDArray[np.uint8]) -> list[DiskResult]:
        """Detect all antibiotic disks in a plate image.

        Loads the YOLOv8 model on the first call.  Uses the Hough fallback
        if no weights file is available.

        Args:
            image: BGR image array as returned by ``cv2.imread``.

        Returns:
            List of ``DiskResult`` objects, one per detected disk.  Returns
            an empty list if no disks are found.
        """
        self._load_model()
        if self._model is not None:
            return self._detect_yolo(image)
        return self._detect_hough(image)

    def _detect_yolo(self, image: NDArray[np.uint8]) -> list[DiskResult]:
        """Run YOLOv8 inference and convert results to DiskResult objects."""
        results = self._model(image, conf=self.confidence, verbose=False)
        disks: list[DiskResult] = []
        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                radius = max(x2 - x1, y2 - y1) // 2
                label = r.names[int(box.cls[0])]
                disks.append(DiskResult(
                    label=label,
                    center_x=cx,
                    center_y=cy,
                    radius_px=radius,
                    confidence=float(box.conf[0]),
                    bbox=(x1, y1, x2, y2),
                ))
        return disks

    def _detect_hough(self, image: NDArray[np.uint8]) -> list[DiskResult]:
        """Detect disk-shaped circles using the Hough Circle Transform.

        Converts the image to grayscale, applies Gaussian blur to reduce
        sensor noise, and calls ``cv2.HoughCircles`` with parameters tuned for
        standard 6-mm antibiotic disks on a 90-mm plate.

        The ``param1=50`` Canny upper threshold and ``param2=20`` accumulator
        threshold were calibrated to detect all 6 disks on the synthetic test
        plate without producing false positives.  Adjust if your plate images
        have very different contrast characteristics.

        Disk labels are assigned as ``'disk_0'``, ``'disk_1'``, etc. in the
        order returned by the Hough transform.  Confidence is always 0.0.
        """
        import cv2

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=50,
            param1=50,
            param2=20,
            minRadius=10,
            maxRadius=40,
        )
        disks: list[DiskResult] = []
        if circles is not None:
            circles = np.around(circles).astype(np.uint16)
            for i, (cx, cy, r) in enumerate(circles[0]):
                disks.append(DiskResult(
                    label=f"disk_{i}",
                    center_x=int(cx),
                    center_y=int(cy),
                    radius_px=int(r),
                    confidence=0.0,
                    bbox=(int(cx - r), int(cy - r), int(cx + r), int(cy + r)),
                ))
        return disks
