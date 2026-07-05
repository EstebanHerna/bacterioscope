"""End-to-end BacterioScope analysis pipeline.

This is the central module of the project.  It chains the four analysis steps
into a single ``.analyze()`` call:

.. code-block:: text

    Image file
        │
        ▼
    calibrate_px_per_mm()   ← detects plate boundary, computes px/mm ratio
        │
        ▼
    DiskDetector.detect()   ← locates each antibiotic disk (YOLOv8 or Hough)
        │
        ▼ (one call per disk)
    ZoneSegmenter.segment() ← measures the inhibition zone diameter in mm
        │
        ▼ (one call per disk)
    CLSIClassifier.classify() ← compares diameter to CLSI 2023 breakpoints
        │                        and returns S / I / R
        ▼
    draw_results()           ← annotates a copy of the image with circles
        │                        and labels
        ▼
    AnalysisResult           ← returned to the caller

Typical usage
-------------
::

    from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig

    pipeline = BacterioScopePipeline(PipelineConfig(plate_diameter_mm=90.0))
    result = pipeline.analyze("plate.jpg")

    for item in result.classifications:
        print(item.antibiotic, item.zone_diameter_mm, item.category)
        # e.g.: ciprofloxacin  26.1  S

The Streamlit demo (``app.py``) and the REST API (``api/routes.py``) both use
this pipeline directly.
"""

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
    """Configuration for a ``BacterioScopePipeline`` instance.

    All fields have sensible defaults for a standard 90-mm Mueller-Hinton
    Petri dish and Enterobacteriaceae breakpoints.

    Attributes:
        detector_weights: Path to the YOLOv8 ``.pt`` weights file trained to
            detect antibiotic disks.  If the file does not exist, the pipeline
            falls back to Hough circle detection automatically.
        confidence_threshold: Minimum YOLOv8 confidence score in [0.0, 1.0].
            Detections below this value are discarded.  Does not affect Hough
            mode.  Lower values detect more disks but may introduce false
            positives.
        plate_diameter_mm: Physical diameter of the Petri dish in mm.
            Used to compute the pixel-to-mm calibration ratio.
            Standard Mueller-Hinton plates: 90 mm.
        organism_group: CLSI breakpoint table to use.  Currently only
            ``'Enterobacteriaceae'`` is supported.
        clsi_version: Edition of CLSI M100 to apply.  Currently ``'2023'``
            (M100-Ed33).
    """
    detector_weights: Path = Path("data/models/yolov8_disks.pt")
    confidence_threshold: float = 0.5
    plate_diameter_mm: float = 90.0
    organism_group: str = "Enterobacteriaceae"
    clsi_version: str = "2023"


@dataclass
class AnalysisResult:
    """Complete output from one BacterioScope pipeline run.

    The three list fields (``disks``, ``zones``, ``classifications``) are
    **parallel** — index ``i`` in each list refers to the same physical
    antibiotic disk on the plate.

    Attributes:
        image_path: Absolute path of the input image file.
        plate_diameter_px: Detected plate diameter in pixels.  Divide by
            ``px_per_mm`` to verify it matches the expected physical size.
        px_per_mm: Calibration factor — pixels per millimetre.  Divide any
            pixel measurement by this value to convert to millimetres.
        disks: One ``DiskResult`` per detected disk.  Contains position,
            size, label, and confidence.
        zones: One ``ZoneResult`` per disk.  Contains the inhibition zone
            diameter in both pixels and mm.
        classifications: One ``SusceptibilityResult`` per disk.  Contains
            the antibiotic name, zone diameter, S/I/R category, and the CLSI
            breakpoint thresholds used.
        annotated_image: BGR copy of the input image with coloured circles
            and text labels drawn by ``draw_results()``.  ``None`` if
            annotation failed.
    """
    image_path: str
    plate_diameter_px: float
    px_per_mm: float
    disks: list[DiskResult] = field(default_factory=list)
    zones: list[ZoneResult] = field(default_factory=list)
    classifications: list[SusceptibilityResult] = field(default_factory=list)
    annotated_image: NDArray[np.uint8] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise the analysis result to a JSON-compatible dictionary.

        Returns:
            Dictionary with keys: ``image_path``, ``plate_diameter_px``,
            ``px_per_mm``, and ``results`` (a list of per-disk records with
            antibiotic name, zone diameter, classification, and breakpoints).
        """
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
    """End-to-end antibiogram analysis pipeline.

    Instantiate once and call ``analyze()`` for each plate image.  All four
    analysis components are initialised at construction time and reused across
    calls, so the YOLOv8 model is loaded only once.

    Example::

        pipeline = BacterioScopePipeline()
        result = pipeline.analyze("plate.jpg")
        for r in result.classifications:
            print(r.antibiotic, r.zone_diameter_mm, r.category)

    Attributes:
        config: Active configuration (see ``PipelineConfig``).
        detector: ``DiskDetector`` instance for this pipeline.
        segmenter: ``ZoneSegmenter`` instance for this pipeline.
        classifier: ``CLSIClassifier`` instance for this pipeline.
    """
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
        """Run the complete analysis pipeline on one plate image file.

        Steps performed in order:

        1. Validate the file (exists, supported format, size ≤ 50 MB).
        2. Load the image with OpenCV.
        3. Detect the plate rim and compute the px/mm calibration ratio.
        4. Locate antibiotic disks (YOLOv8 or Hough fallback).
        5. Segment the inhibition zone for each disk and measure its diameter.
        6. Classify each diameter against CLSI 2023 breakpoints (S/I/R).
        7. Draw annotations on a copy of the image.

        Args:
            image_path: Path to the plate image.  Supported formats: JPEG,
                PNG, BMP, TIFF.  Maximum file size: 50 MB.

        Returns:
            ``AnalysisResult`` containing detected disks, zone measurements,
            S/I/R classifications, and the annotated image.

        Raises:
            FileNotFoundError: If ``image_path`` does not point to an
                existing file.
            ValueError: If the file format is unsupported, exceeds 50 MB,
                or cannot be decoded by OpenCV.
        """
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
