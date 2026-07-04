from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from bacterioscope.classification.clsi import CLSIClassifier, SusceptibilityResult
from bacterioscope.detection.detector import DiskDetector, DiskResult
from bacterioscope.segmentation.watershed import ZoneResult, ZoneSegmenter
from bacterioscope.utils.calibration import calibrate_px_per_mm
from bacterioscope.utils.visualization import draw_results


@dataclass
class PipelineConfig:
    detector_weights: Path = Path("data/models/yolov8_disks.pt")
    confidence_threshold: float = 0.5
    plate_diameter_mm: float = 90.0
    organism_group: str = "Enterobacteriaceae"
    clsi_version: str = "2023"


@dataclass
class AnalysisResult:
    image_path: str
    plate_diameter_px: float
    px_per_mm: float
    disks: list[DiskResult] = field(default_factory=list)
    zones: list[ZoneResult] = field(default_factory=list)
    classifications: list[SusceptibilityResult] = field(default_factory=list)
    annotated_image: NDArray[np.uint8] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_path": self.image_path,
            "plate_diameter_px": round(self.plate_diameter_px, 1),
            "px_per_mm": round(self.px_per_mm, 3),
            "results": [
                {
                    "antibiotic": cls.antibiotic,
                    "zone_diameter_mm": round(cls.zone_diameter_mm, 1),
                    "classification": cls.category,
                    "breakpoints": cls.breakpoints,
                }
                for cls in self.classifications
            ],
        }


_ALLOWED_SUFFIXES: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
)
_MAX_IMAGE_BYTES: int = 50 * 1024 * 1024  # 50 MB


class BacterioScopePipeline:
    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self.detector = DiskDetector(
            weights=self.config.detector_weights,
            confidence=self.config.confidence_threshold,
        )
        self.segmenter = ZoneSegmenter()
        self.classifier = CLSIClassifier(
            organism_group=self.config.organism_group,
            version=self.config.clsi_version,
        )

    def analyze(self, image_path: str | Path) -> AnalysisResult:
        image_path = Path(image_path)
        if not image_path.is_file():
            raise FileNotFoundError(f"Image not found: {image_path}")
        if image_path.suffix.lower() not in _ALLOWED_SUFFIXES:
            raise ValueError(f"Unsupported image format: {image_path.suffix!r}")
        if image_path.stat().st_size > _MAX_IMAGE_BYTES:
            raise ValueError(f"Image exceeds 50 MB size limit: {image_path}")
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Could not decode image: {image_path}")

        plate_diameter_px, px_per_mm = calibrate_px_per_mm(
            image, self.config.plate_diameter_mm
        )

        disks = self.detector.detect(image)

        zones = []
        for disk in disks:
            zone = self.segmenter.segment(image, disk, px_per_mm)
            zones.append(zone)

        classifications = []
        for disk, zone in zip(disks, zones):
            result = self.classifier.classify(
                antibiotic=disk.label,
                zone_diameter_mm=zone.diameter_mm,
            )
            classifications.append(result)

        annotated = draw_results(image.copy(), disks, zones, classifications)

        return AnalysisResult(
            image_path=str(image_path),
            plate_diameter_px=plate_diameter_px,
            px_per_mm=px_per_mm,
            disks=disks,
            zones=zones,
            classifications=classifications,
            annotated_image=annotated,
        )
