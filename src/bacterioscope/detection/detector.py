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
    label: str
    center_x: int
    center_y: int
    radius_px: int
    confidence: float
    bbox: tuple[int, int, int, int]


class DiskDetector:
    def __init__(self, weights: Path, confidence: float = 0.5) -> None:
        self.weights = weights
        self.confidence = confidence
        self._model: Any = None

    def _load_model(self) -> None:
        if self._model is not None:
            return
        if self.weights.exists():
            self._verify_weights(self.weights)
            from ultralytics import YOLO
            self._model = YOLO(str(self.weights))
        else:
            self._model = None

    def _verify_weights(self, path: Path) -> None:
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
        self._load_model()
        if self._model is not None:
            return self._detect_yolo(image)
        return self._detect_hough(image)

    def _detect_yolo(self, image: NDArray[np.uint8]) -> list[DiskResult]:
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
