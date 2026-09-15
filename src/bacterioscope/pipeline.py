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

import hashlib
import logging
import subprocess  # nosec B404
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from bacterioscope.classification.clsi import (
    BREAKPOINT_TABLE_VERSION,
    CLSIClassifier,
    SusceptibilityResult,
)
from bacterioscope.detection.detector import DiskDetector, DiskResult
from bacterioscope.segmentation.watershed import ZoneResult, ZoneSegmenter
from bacterioscope.utils.calibration import (
    calibrate_from_disk_radius_px,
    calibrate_px_per_mm,
    refine_disk_radius_px,
)
from bacterioscope.utils.image import load_image, resize_canonical
from bacterioscope.utils.visualization import draw_results, has_watermark

log = logging.getLogger(__name__)

_SOFTWARE_VERSION: str = "0.1.0"

# How far a zone's fitted circle may extend past the image edge before the
# 'boundary' quality flag fires. See _compute_flags() for why zero tolerance
# was too strict in practice.
_BOUNDARY_TOLERANCE_PX: int = 15

# Fraction of a zone mask's own bounding-box area it may fill before the
# 'crop_boundary' quality flag fires. Chosen from a real sweep (0.75-1.01),
# not assumed: circularity alone does not predict error (it is non-monotonic
# -- the 0.70-0.82 band measures worse than both lower and higher bands), but
# a mask filling nearly all of its search crop is the confirmed signature of
# tracing the crop's own edge rather than a biological one. At this ceiling,
# on the 316-pair identity-matched set, Essential Agreement for the
# unflagged measurements is 42.8% against a 32.9% baseline for all of them
# (173 pairs kept, 45.3% flagged) -- a real, measured improvement, not a
# guess. See scripts/measure_confidence_indicator.py to reproduce the sweep.
_CROP_FILL_CEILING: float = 0.90


def _crop_fill_ratio(mask: NDArray[np.uint8] | None) -> float | None:
    """Return the fraction of a zone mask's own bounding box that it fills.

    A value near 1.0 means the traced contour is most likely the edge of the
    search crop rather than a real inhibition-zone boundary -- see the
    ``crop_boundary`` flag in ``_compute_flags()``.

    Args:
        mask: Binary zone mask (255 = zone interior), or ``None`` if no zone
            was found for this disk.

    Returns:
        Fill ratio in ``[0, 1]``, or ``None`` if there is no mask or its
        bounding box has zero area.
    """
    if mask is None:
        return None
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    bbox_area = (xs.max() - xs.min()) * (ys.max() - ys.min())
    if bbox_area == 0:
        return None
    return float((mask.sum() / 255) / bbox_area)


def _get_commit_hash() -> str:
    """Return the current git short hash, or 'unknown' if git is unavailable."""
    # Fixed argv, no shell, no user input -- safe for traceability metadata only.
    try:
        proc = subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        log.debug("git rev-parse unavailable; commit hash will be 'unknown'.")
    return "unknown"


def _compute_image_sha256(image_path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with image_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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
            mode.  Kept at a defensible floor (0.25): the 29-class detector's
            maximum observed confidence on real photos is ~0.05, so anything
            it reports above that is model noise, not a real detection --
            and because the hybrid fallback only tries Hough when YOLO finds
            nothing, a single noisy YOLO detection can silently pre-empt 16
            reliable Hough detections (see docs/VALIDATION_REPORT.md). Do not
            lower this to force detections out of an undertrained model; use
            Hough (the current default fallback) or train a better model.
        plate_diameter_mm: Physical diameter of the Petri dish in mm.
            Used to compute the pixel-to-mm calibration ratio.
            Standard Mueller-Hinton plates: 90 mm.
        organism_group: CLSI breakpoint table to use.  Currently only
            ``'Enterobacteriaceae'`` is supported.
        clsi_version: Edition of CLSI M100 to apply.  Currently ``'2023'``
            (M100-Ed33).
        use_disk_calibration: If ``True`` and at least one disk is detected,
            derive px/mm from the median disk radius (re-measured
            independently via ``calibration.py::refine_disk_radius_px()``,
            not the detector's own radius) using the known 6 mm physical
            disk diameter (CLSI M02) instead of plate-rim Hough detection.
            Measured directly on 80 real UZH photos: even with an
            unbiased, independent measurement, this underperforms
            plate-rim calibration (identity-matched EA 28.8% vs 32.9%) --
            not a bug, a consequence of calibrating against a ~50-60px
            reference (the disk) instead of a ~550-600px one (the plate),
            which makes the same few pixels of edge noise a proportionally
            larger calibration error.  Defaults to ``False``.
        disk_diameter_mm: Physical diameter of a standard antibiotic disk in
            mm.  Used when ``use_disk_calibration`` is ``True``, and always
            used to derive the calibrated Hough disk-search radius (see
            ``detector.py``).
        canonical_resize_enabled: If ``True`` (default), downscale the image
            so its longer side is at most ``canonical_max_dimension`` before
            calibration and detection.  Never upscales, so small synthetic
            test plates are unaffected.  Brings phone photos (up to ~4128 px)
            and dataset images (640-1024 px) into a shared pixel-scale
            ballpark so one geometry parameter set works across cameras.
        canonical_max_dimension: Longer-side target in pixels for the
            canonical resize.  Only used when ``canonical_resize_enabled``.
    """
    detector_weights: Path = Path("data/models/yolov8_disks.pt")
    confidence_threshold: float = 0.25
    plate_diameter_mm: float = 90.0
    organism_group: str = "Enterobacteriaceae"
    clsi_version: str = "2023"
    use_disk_calibration: bool = False
    disk_diameter_mm: float = 6.0
    canonical_resize_enabled: bool = True
    canonical_max_dimension: int = 1400


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
        plate_center: (x, y) pixel coordinates of the estimated plate centre.
            Computed as the centroid of detected disks, or the image centre
            when no disks are found.  Used by PanelManager for angular
            disk-position assignment.
        canonical_scale_factor: Ratio applied by the canonical resize step
            (resized_side / original_side).  ``1.0`` when the input was
            already at or below ``canonical_max_dimension``, or resizing was
            disabled.  All pixel/mm fields on this result are expressed in
            the (possibly resized) canonical image space.
        disk_calibration_ratio: Median detected disk diameter (mm) divided
            by the expected physical disk diameter (normally 6.0). ``1.0``
            means calibration and disk-radius estimation agree with the
            known physical disk size; ``None`` when no disks were detected.
            A value that deviates consistently from 1.0 across many images
            signals a systematic calibration or detection-radius bias.
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
    plate_center: tuple[int, int] = field(default_factory=lambda: (0, 0))
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    software_version: str = ""
    commit_hash: str = "unknown"
    breakpoint_table_version: str = ""
    image_sha256: str = ""
    timings_ms: dict[str, float] = field(default_factory=dict)
    canonical_scale_factor: float = 1.0
    disk_calibration_ratio: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise the analysis result to a JSON-compatible dictionary.

        Returns:
            Dictionary with keys: ``image_path``, ``plate_diameter_px``,
            ``px_per_mm``, and ``results`` (per-disk records with antibiotic
            name, zone diameter, classification, breakpoints, and flags).
        """
        return {
            "analysis_id": self.analysis_id,
            "software_version": self.software_version,
            "commit_hash": self.commit_hash,
            "breakpoint_table_version": self.breakpoint_table_version,
            "image_sha256": self.image_sha256,
            "timings_ms": {k: round(v, 1) for k, v in self.timings_ms.items()},
            "image_path": self.image_path,
            "plate_diameter_px": round(self.plate_diameter_px, 1),
            "px_per_mm": round(self.px_per_mm, 3),
            "canonical_scale_factor": round(self.canonical_scale_factor, 4),
            "disk_calibration_ratio": (
                round(self.disk_calibration_ratio, 3)
                if self.disk_calibration_ratio is not None
                else None
            ),
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


def _estimate_plate_center(
    disks: list[DiskResult],
    image_shape: tuple[int, ...],
) -> tuple[int, int]:
    """Estimate the plate centre from disk centroids or image centre.

    Args:
        disks: Detected disks (may be empty).
        image_shape: (height, width, ...) of the image array.

    Returns:
        (x, y) pixel coordinates of the estimated plate centre.
    """
    h, w = image_shape[:2]
    if disks:
        cx = int(np.mean([d.center_x for d in disks]))
        cy = int(np.mean([d.center_y for d in disks]))
        return cx, cy
    return w // 2, h // 2


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
            disk_diameter_mm=self.config.disk_diameter_mm,
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
        t0 = time.perf_counter()
        image_path = Path(image_path)
        image = load_image(image_path)
        if has_watermark(image):
            raise ValueError(
                f"{image_path.name} already carries a BacterioScope output watermark "
                "(top-left corner marker) -- it looks like an annotated result, not a "
                "raw photograph. Upload the original, unprocessed image instead."
            )
        if self.config.canonical_resize_enabled:
            image, scale_factor = resize_canonical(image, self.config.canonical_max_dimension)
        else:
            scale_factor = 1.0
        t_load = time.perf_counter()

        plate_diameter_px, px_per_mm = calibrate_px_per_mm(image, self.config.plate_diameter_mm)
        t_cal = time.perf_counter()

        disks = self.detector.detect(image, px_per_mm=px_per_mm)
        t_det = time.perf_counter()

        if self.config.use_disk_calibration and disks:
            median_radius = refine_disk_radius_px(image, disks)
            px_per_mm = calibrate_from_disk_radius_px(median_radius, self.config.disk_diameter_mm)

        disk_calibration_ratio = self._disk_calibration_ratio(disks, px_per_mm)

        original = image.copy()
        zones = self._segment_all(image, disks, px_per_mm)
        t_seg = time.perf_counter()

        classifications = self._classify_all(disks, zones)
        flags = self._compute_flags(disks, zones, image.shape)
        t_cls = time.perf_counter()

        annotated = draw_results(image.copy(), disks, zones, classifications, flags)
        plate_center = _estimate_plate_center(disks, image.shape)
        t_end = time.perf_counter()

        def _ms(a: float, b: float) -> float:
            return round((b - a) * 1000.0, 1)

        timings: dict[str, float] = {
            "load_ms": _ms(t0, t_load),
            "calibrate_ms": _ms(t_load, t_cal),
            "detect_ms": _ms(t_cal, t_det),
            "segment_ms": _ms(t_det, t_seg),
            "classify_ms": _ms(t_seg, t_cls),
            "annotate_ms": _ms(t_cls, t_end),
            "total_ms": _ms(t0, t_end),
        }
        log.debug(
            "analyze timing: %s  disks=%d",
            " ".join(f"{k}={v}" for k, v in timings.items()),
            len(disks),
        )

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
            plate_center=plate_center,
            software_version=_SOFTWARE_VERSION,
            commit_hash=_get_commit_hash(),
            breakpoint_table_version=BREAKPOINT_TABLE_VERSION,
            image_sha256=_compute_image_sha256(image_path),
            timings_ms=timings,
            canonical_scale_factor=scale_factor,
            disk_calibration_ratio=disk_calibration_ratio,
        )

    def _disk_calibration_ratio(
        self,
        disks: list[DiskResult],
        px_per_mm: float,
    ) -> float | None:
        """Compare median detected disk size against the known physical size.

        A diagnostic signal, not used to correct measurements automatically.
        See ``AnalysisResult.disk_calibration_ratio`` for interpretation.

        Args:
            disks: Detected disks for this image.
            px_per_mm: Calibration factor currently in effect.

        Returns:
            Ratio of median detected disk diameter (mm) to
            ``config.disk_diameter_mm``, or ``None`` if no disks were found.
        """
        if not disks or px_per_mm <= 0:
            return None
        diameters_mm = [(2.0 * d.radius_px) / px_per_mm for d in disks]
        return float(np.median(diameters_mm)) / self.config.disk_diameter_mm

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
        return self.segmenter.segment_all(image, disks, px_per_mm)

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
            boundary: zone extends more than ``_BOUNDARY_TOLERANCE_PX`` beyond
                the image edge, truncating the measurement. The tolerance
                exists because a zero-tolerance check flagged 45% of disks on
                a 20-image real-photo audit, with a median overshoot of only
                12px on a ~1024px-wide image (~1%) -- ordinary fitted-circle
                rounding noise on a dense grid, not a truncated measurement.
                Overshoots that are actually severe (seen up to 75px in the
                same audit) still flag.
            crop_boundary: the zone mask fills more than
                ``_CROP_FILL_CEILING`` of its own bounding-box area, meaning
                the measured contour is most likely the edge of the search
                crop, not a real inhibition-zone edge. Measured, not assumed,
                to be a real confidence signal: unflagged measurements score
                substantially higher Essential Agreement than flagged ones at
                every ceiling tried (see ``_CROP_FILL_CEILING``).
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
                overshoot = max(
                    -(zone.center_x - r), -(zone.center_y - r),
                    (zone.center_x + r) - w, (zone.center_y + r) - h,
                )
                if overshoot > _BOUNDARY_TOLERANCE_PX:
                    flags[i].append("boundary")
            fill_ratio = _crop_fill_ratio(zone.mask)
            if fill_ratio is not None and fill_ratio >= _CROP_FILL_CEILING:
                flags[i].append("crop_boundary")
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

    def reclassify_with_labels(
        self,
        result: AnalysisResult,
        labels: list[str],
    ) -> AnalysisResult:
        """Return a new AnalysisResult with antibiotics replaced by labels.

        Used after panel assignment to re-run the CLSI classifier with the
        panel-assigned antibiotic names.  All other fields are copied from
        the original result unchanged.

        Args:
            result: Completed AnalysisResult from analyze().
            labels: Antibiotic names in pipeline disk order (same length as
                result.disks).

        Returns:
            New AnalysisResult with updated classifications.
        """
        new_cls = [
            self.classifier.classify(antibiotic=label, zone_diameter_mm=z.diameter_mm)
            for label, z in zip(labels, result.zones)
        ]
        return AnalysisResult(
            image_path=result.image_path,
            plate_diameter_px=result.plate_diameter_px,
            px_per_mm=result.px_per_mm,
            disks=result.disks,
            zones=result.zones,
            classifications=new_cls,
            annotated_image=result.annotated_image,
            original_image=result.original_image,
            flags=result.flags,
            plate_center=result.plate_center,
        )

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
