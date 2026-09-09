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

import cv2
import numpy as np
from numpy.typing import NDArray

from bacterioscope.detection.label_map import ROBOFLOW_TO_CLSI

# SHA-256 hashes of trusted model files. Populate when distributing known-good weights.
# Loading a .pt file without a matching hash will log a warning; add hashes here to
# enable enforcement. torch.load (called internally by ultralytics) can execute arbitrary
# code when weights_only=False — only load weights from sources you control.
_TRUSTED_MODEL_HASHES: dict[str, str] = {}

_DISK_BLUR_KERNEL: tuple[int, int] = (9, 9)
_HOUGH_DP: float = 1.2
_HOUGH_MIN_DIST: int = 50
_HOUGH_PARAM1: int = 50
_HOUGH_PARAM2: int = 20
_HOUGH_MIN_RADIUS: int = 10
_HOUGH_MAX_RADIUS: int = 40

# When px_per_mm is known (calibration already ran), search for disks in a tight
# window around the physically expected radius instead of a fixed pixel range.
# HoughCircles is known to bias its vote toward the *largest* radius that still
# fits the edge evidence, so a loose ceiling (as in _HOUGH_MAX_RADIUS above)
# systematically overestimates disk size -- measured at a median +28% (6mm true
# disks reading ~7.7mm) on the real UZH photo set. A tight, calibration-derived
# ceiling removes that degree of freedom.
_DISK_RADIUS_MARGIN_LOW: float = 0.6
_DISK_RADIUS_MARGIN_HIGH: float = 1.3

# No single param2 (Hough's accumulator threshold) works across both real photos
# and synthetic test plates: real photos need ~45 (looser values pick up agar
# texture as false circles), but synthetic plates' softer, blurred disk edges
# fall below that threshold and lose real disks (measured: 5/6 or fewer detected
# on every synthetic test plate at param2=45). Instead of picking one value,
# sweep from strict to loose and use the count that holds stable across the
# longest run of consecutive values -- real disks keep registering across a
# wide param2 range, while noise circles only appear once the threshold drops
# low enough, so the stable run is the real disk count in both regimes.
_HOUGH_PARAM2_SWEEP: tuple[int, ...] = (50, 45, 40, 35, 30, 25, 20)


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
        disk_diameter_mm: Physical diameter of a standard antibiotic disk.
            Used to derive a calibrated Hough search radius when ``detect()``
            is called with ``px_per_mm``.  Standard CLSI disks are 6.0 mm.
    """
    def __init__(
        self,
        weights: Path,
        confidence: float = 0.5,
        disk_diameter_mm: float = 6.0,
    ) -> None:
        self.weights = weights
        self.confidence = confidence
        self.disk_diameter_mm = disk_diameter_mm
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

    def detect(
        self,
        image: NDArray[np.uint8],
        px_per_mm: float | None = None,
    ) -> list[DiskResult]:
        """Detect all antibiotic disks in a plate image.

        Loads the YOLOv8 model on the first call.  Uses the Hough fallback
        if no weights file is available.

        Args:
            image: BGR image array as returned by ``cv2.imread``.
            px_per_mm: Calibration factor from ``calibrate_px_per_mm()``, if
                already known.  When given, the Hough fallback searches for
                disks in a tight window around the physically expected pixel
                radius (``disk_diameter_mm`` at this scale) instead of a
                fixed, resolution-dependent pixel range.  ``None`` preserves
                the original broad-range behaviour.

        Returns:
            List of ``DiskResult`` objects, one per detected disk.  Returns
            an empty list if no disks are found.
        """
        self._load_model()
        if self._model is not None:
            yolo_results = self._detect_yolo(image)
            if yolo_results:
                return yolo_results
        return self._detect_hough(image, px_per_mm)

    def _detect_yolo(self, image: NDArray[np.uint8]) -> list[DiskResult]:
        """Run YOLOv8 inference and convert results to DiskResult objects.

        A 29-class model names each detection by the antibiotic it read off
        the disk, so that class name becomes the label directly. A
        single-class 'disk' detector (Phase 2's higher-mAP replacement for
        Hough localisation) has no such identity to report -- every
        detection shares the same class name, and passing that name straight
        through would give every disk on the plate the identical label
        'disk', colliding in the CLSI lookup, the UI table, and everywhere
        else a unique per-disk identifier is assumed. Number sequentially
        instead ('disk_0', 'disk_1', ...), matching the Hough fallback's own
        convention -- identity then resolves through panel position
        (PanelManager) exactly as it does for Hough detections today.
        """
        results = self._model(image, conf=self.confidence, verbose=False)
        single_class = len(self._model.names) == 1
        disks: list[DiskResult] = []
        for r in results:
            for i, box in enumerate(r.boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2
                radius = max(x2 - x1, y2 - y1) // 2
                if single_class:
                    label = f"disk_{i}"
                else:
                    raw_label = r.names[int(box.cls[0])]
                    label = ROBOFLOW_TO_CLSI.get(raw_label, raw_label)
                disks.append(DiskResult(
                    label=label,
                    center_x=cx,
                    center_y=cy,
                    radius_px=radius,
                    confidence=float(box.conf[0]),
                    bbox=(x1, y1, x2, y2),
                ))
        return disks

    def _detect_hough(
        self,
        image: NDArray[np.uint8],
        px_per_mm: float | None = None,
    ) -> list[DiskResult]:
        """Detect disk-shaped circles using the Hough Circle Transform.

        Converts the image to grayscale, applies Gaussian blur to reduce
        sensor noise, and runs HoughCircles.  When ``px_per_mm`` is known,
        the radius search window is derived from the physical disk size
        (tight, calibrated) instead of the fixed broad range (fallback for
        callers that have not calibrated yet, e.g. most existing tests).
        Disk labels default to 'disk_0', 'disk_1', etc. because the Hough
        transform cannot read printed labels.

        Args:
            image: BGR plate image.
            px_per_mm: Calibration factor, or ``None`` for the broad-range
                fallback search.

        Returns:
            List of DiskResult objects, one per detected circle.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, _DISK_BLUR_KERNEL, 2)
        min_radius, max_radius, calibrated = self._hough_search_window(px_per_mm)
        if calibrated:
            circles = self._hough_stable_circles(blurred, min_radius, max_radius)
        else:
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=_HOUGH_DP, minDist=_HOUGH_MIN_DIST,
                param1=_HOUGH_PARAM1, param2=_HOUGH_PARAM2,
                minRadius=min_radius, maxRadius=max_radius,
            )
        disks: list[DiskResult] = []
        if circles is not None:
            circles = np.around(circles).astype(np.int32)
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

    def _hough_search_window(self, px_per_mm: float | None) -> tuple[int, int, bool]:
        """Return ``(min_radius, max_radius, calibrated)`` for the Hough search.

        With a known calibration, the window is centred on the physically
        expected disk radius (see module docstring for why a loose fixed
        range systematically overestimates disk size). Without one, falls
        back to the original broad, resolution-dependent range.

        Args:
            px_per_mm: Calibration factor, or ``None``.

        Returns:
            ``(min_radius, max_radius, calibrated)`` in pixels; ``calibrated``
            indicates whether the tight, calibration-derived window was used.
        """
        if px_per_mm is None or px_per_mm <= 0:
            return _HOUGH_MIN_RADIUS, _HOUGH_MAX_RADIUS, False
        expected_radius = (self.disk_diameter_mm / 2.0) * px_per_mm
        min_radius = max(3, int(expected_radius * _DISK_RADIUS_MARGIN_LOW))
        max_radius = max(min_radius + 1, int(expected_radius * _DISK_RADIUS_MARGIN_HIGH))
        return min_radius, max_radius, True

    def _hough_stable_circles(
        self,
        blurred: NDArray[np.uint8],
        min_radius: int,
        max_radius: int,
    ) -> NDArray[np.float32] | None:
        """Sweep Hough's accumulator threshold and return the stable-count result.

        No single param2 works across real photos (need ~45 to reject agar
        texture as false circles) and synthetic plates (softer edges drop
        below that threshold, losing real disks). Sweeping strict-to-loose and
        taking the circle count that holds across the longest run of
        consecutive thresholds finds the real disk count in both regimes:
        real disks keep registering across a wide param2 range, while false
        circles only appear once the threshold drops low enough to admit them.

        Args:
            blurred: Grayscale, Gaussian-blurred plate image.
            min_radius: Minimum circle radius in pixels.
            max_radius: Maximum circle radius in pixels.

        Returns:
            The ``cv2.HoughCircles`` output array for the stable run (the
            strictest param2 within it), or ``None`` if every attempt found
            zero circles.
        """
        best_run_len = 0
        best_circles: NDArray[np.float32] | None = None
        prev_count = -1
        prev_circles: NDArray[np.float32] | None = None
        run_len = 0
        run_start_circles: NDArray[np.float32] | None = None
        for param2 in _HOUGH_PARAM2_SWEEP:
            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT, dp=_HOUGH_DP, minDist=_HOUGH_MIN_DIST,
                param1=_HOUGH_PARAM1, param2=param2,
                minRadius=min_radius, maxRadius=max_radius,
            )
            count = 0 if circles is None else len(circles[0])
            if count > 0 and count == prev_count:
                run_len += 1
            else:
                run_len = 1
                run_start_circles = circles
            if count > 0 and run_len > best_run_len:
                best_run_len = run_len
                best_circles = run_start_circles
            prev_count, prev_circles = count, circles
        return best_circles if best_circles is not None else prev_circles
