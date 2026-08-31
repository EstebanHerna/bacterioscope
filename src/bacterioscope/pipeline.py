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

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from bacterioscope.classification.clsi import CLSIClassifier, SusceptibilityResult
from bacterioscope.detection.detector import DiskDetector, DiskResult
from bacterioscope.segmentation.watershed import ZoneResult, ZoneSegmenter
from bacterioscope.utils.calibration import calibrate_from_disk_radius_px, calibrate_px_per_mm
from bacterioscope.utils.image import load_image
from bacterioscope.utils.visualization import draw_results

log = logging.getLogger(__name__)


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
        use_disk_calibration: If ``True`` and at least one disk is detected,
            derive px/mm from the median disk radius using the known 6 mm
            physical disk diameter (CLSI M02) instead of plate-rim Hough
            detection.  More robust under variable lighting.  Defaults to
            ``False`` for backwards compatibility.
        disk_diameter_mm: Physical diameter of a standard antibiotic disk in
            mm.  Used only when ``use_disk_calibration`` is ``True``.
            Change only for non-standard consumables.
    """
    detector_weights: Path = Path("data/models/yolov8_disks.pt")
    confidence_threshold: float = 0.5
    plate_diameter_mm: float = 90.0
    organism_group: str = "Enterobacteriaceae"
    clsi_version: str = "2023"
    use_disk_calibration: bool = False
    disk_diameter_mm: float = 6.0


@dataclass
class AnalysisResult:
    """Complete output from one BacterioScope pipeline run.

    The four list fields (``disks``, ``zones``, ``classifications``, ``flags``)
    are **parallel** — index ``i`` in each list refers to the same physical
    antibiotic disk on the plate.

    Attributes:
        image_path: Absolute path of the input image file.
        plate_diameter_px: Detected plate diameter in pixels.
        px_per_mm: Calibration factor — pixels per millimetre.
        disks: One ``DiskResult`` per detected disk.
        zones: One ``ZoneResult`` per disk — zone diameter in pixels and mm.
        classifications: One ``SusceptibilityResult`` per disk — S/I/R category
            and CLSI breakpoint thresholds.
        annotated_image: BGR copy of the input image with contours and labels
            drawn by ``draw_results()``.  ``None`` if annotation failed.
        original_image: Unmodified BGR copy of the input image, stored for
            the UI's opacity/toggle visualisation controls.  ``None`` if the
            image could not be stored (e.g. memory constraints).
        flags: One list of flag strings per disk.  Possible flags:
            ``'low_circularity'``, ``'small_zone'``, ``'boundary'``,
            ``'overlap'``.  An empty inner list means no quality issues.
    """
    image_path: str
    plate_diameter_px: float
    px_per_mm: float
    disks: list[DiskResult] = field(default_factory=list)
    zones: list[ZoneResult] = field(default_factory=list)
    classifications: list[SusceptibilityResult] = field(default_factory=list)
    annotated_image: NDArray[np.uint8] | None = None
    original_image: NDArray[np.uint8] | None = None
    flags: list[list[str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialise the analysis result to a JSON-compatible dictionary.

        Returns:
            Dictionary with keys: ``image_path``, ``plate_diameter_px``,
            ``px_per_mm``, and ``results`` (per-disk records with antibiotic
            name, zone diameter, classification, breakpoints, and flags).
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
                    "flags": self.flags[i] if i < len(self.flags) else [],
                }
                for i, cls in enumerate(self.classifications)
            ],
        }


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
        image = load_image(image_path)

        plate_diameter_px, px_per_mm = calibrate_px_per_mm(image, self.config.plate_diameter_mm)
        disks = self.detector.detect(image)

        if self.config.use_disk_calibration and disks:
            median_radius = float(np.median([d.radius_px for d in disks]))
            px_per_mm = calibrate_from_disk_radius_px(median_radius, self.config.disk_diameter_mm)

        original = image.copy()
        zones = self._segment_all(image, disks, px_per_mm)
        classifications = self._classify_all(disks, zones)
        flags = self._compute_flags(disks, zones, image.shape)
        annotated = draw_results(image.copy(), disks, zones, classifications, flags)

        return AnalysisResult(
            image_path=str(image_path),
            plate_diameter_px=plate_diameter_px,
            px_per_mm=px_per_mm,
            disks=disks,
            zones=zones,
            classifications=classifications,
            annotated_image=annotated,
            original_image=original,
            flags=flags,
        )

    def _segment_all(
        self,
        image: NDArray[np.uint8],
        disks: list[DiskResult],
        px_per_mm: float,
    ) -> list[ZoneResult]:
        """Segment the inhibition zone for every detected disk.

        Args:
            image: Full BGR plate image.
            disks: Detected disk list from DiskDetector.
            px_per_mm: Calibration factor for pixel-to-mm conversion.

        Returns:
            List of ZoneResult objects in the same order as disks.
        """
        return [self.segmenter.segment(image, disk, px_per_mm) for disk in disks]

    def _compute_flags(
        self,
        disks: list[DiskResult],
        zones: list[ZoneResult],
        image_shape: tuple[int, ...],
    ) -> list[list[str]]:
        """Compute quality flags for each disk-zone pair.

        Flags indicate measurements that warrant human review.  An empty inner
        list means no quality issues were detected for that disk.

        Flag meanings:
            low_circularity: zone contour circularity < 0.7, suggesting an
                irregular or asymmetric inhibition pattern.
            small_zone: zone diameter < 6 mm (smaller than the physical disk
                itself), likely a detection error or fully resistant organism.
            boundary: zone extends to or beyond the image edge, truncating the
                measurement.
            overlap: zone overlaps with the zone of an adjacent disk.

        Args:
            disks: Detected disk positions.
            zones: Corresponding zone measurements.
            image_shape: Shape tuple of the full plate image (h, w, ...).

        Returns:
            List of flag lists, one per disk, in the same order as disks.
        """
        h, w = image_shape[:2]
        flags: list[list[str]] = [[] for _ in disks]
        for i, (_, zone) in enumerate(zip(disks, zones)):
            if zone.diameter_mm > 0 and zone.circularity < 0.7:
                flags[i].append("low_circularity")
            if 0 < zone.diameter_mm < 6.0:
                flags[i].append("small_zone")
            if zone.radius_px > 0:
                r = int(zone.radius_px)
                if zone.center_x - r < 0 or zone.center_y - r < 0 \
                        or zone.center_x + r > w or zone.center_y + r > h:
                    flags[i].append("boundary")
        for i in range(len(disks)):
            for j in range(i + 1, len(disks)):
                dist = float(np.sqrt(
                    (disks[i].center_x - disks[j].center_x) ** 2
                    + (disks[i].center_y - disks[j].center_y) ** 2
                ))
                if dist < zones[i].radius_px + zones[j].radius_px:
                    if "overlap" not in flags[i]:
                        flags[i].append("overlap")
                    if "overlap" not in flags[j]:
                        flags[j].append("overlap")
        return flags

    def _classify_all(
        self,
        disks: list[DiskResult],
        zones: list[ZoneResult],
    ) -> list[SusceptibilityResult]:
        """Classify every disk-zone pair against the CLSI breakpoint table.

        Args:
            disks: Detected disks (provides the antibiotic label).
            zones: Corresponding zone measurements (provides diameter_mm).

        Returns:
            List of SusceptibilityResult objects in the same order as disks.
        """
        return [
            self.classifier.classify(
                antibiotic=disk.label,
                zone_diameter_mm=zone.diameter_mm,
            )
            for disk, zone in zip(disks, zones)
        ]

    def analyze_safe(
        self,
        image_path: str | Path,
    ) -> AnalysisResult | None:
        """Run the pipeline without raising — returns None on any failure.

        Intended for batch processing where a single bad image must not abort
        the whole run.  All exceptions are logged at WARNING level with the
        image path and reason so failures can be investigated after the batch.

        Args:
            image_path: Path to the plate image.

        Returns:
            ``AnalysisResult`` on success, ``None`` on any error.
        """
        try:
            return self.analyze(image_path)
        except Exception as exc:
            log.warning("Skipping %s — %s: %s", image_path, type(exc).__name__, exc)
            return None
