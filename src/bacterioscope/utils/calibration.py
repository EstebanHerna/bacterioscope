"""Plate boundary detection and pixel-to-millimetre calibration.

Why calibration is necessary
-----------------------------
A smartphone photograph taken 30 cm above the bench will have a very different
number of pixels per physical millimetre than one taken at 50 cm.  Without
knowing this ratio, the same pixel measurement could correspond to 20 mm in
one photo and 30 mm in another — a clinically significant difference that
would produce the wrong S/I/R category.

How this module solves it
--------------------------
The standard Kirby-Bauer Petri dish is circular with a known physical
diameter (default 90 mm).  Using OpenCV's Hough Circle Transform this module
detects the plate rim in the photograph, measures its pixel diameter, and
divides by the physical diameter::

    px_per_mm = plate_diameter_px / plate_diameter_mm

Every downstream zone measurement divides its pixel value by this factor to
obtain a clinically meaningful millimetre value.

Fallback behaviour
------------------
If the Hough transform finds no circle (unusual lighting, partial plate), the
function falls back to 90 % of the shorter image dimension as an estimate of
the plate diameter.  Results will be less accurate but the pipeline will not
crash.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2
import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from bacterioscope.detection.detector import DiskResult

_PLATE_FALLBACK_FRACTION: float = 0.9

# How far beyond a disk's own Hough-reported radius to crop when
# re-measuring its true edge locally (see refine_disk_radius_px()).
_DISK_REFINE_MARGIN: float = 1.8


def calibrate_from_disk_radius_px(
    disk_radius_px: float,
    disk_diameter_mm: float = 6.0,
) -> float:
    """Compute px/mm using the known physical diameter of an antibiotic disk.

    Every standard antibiotic disk has a physical diameter of exactly 6 mm
    (CLSI M02 / OPS quality-control convention). This is the Phase 3
    calibration method: sharp, high-contrast disk edges should in principle
    be a more reliable reference than the plate rim under variable lighting.

    Measured directly, this theoretical advantage does not hold on the real
    UZH photo set: even with an independently and correctly measured disk
    radius (see ``refine_disk_radius_px()`` -- passing the detector's own,
    non-independent radius here understates the error further), disk
    calibration trails plate-rim calibration (identity-matched EA 28.8% vs
    32.9%, MAE 7.42mm vs 6.28mm). The reason is not sharpness or contrast:
    it is reference size. The plate rim spans roughly 550-600px in a
    canonical-resized image; a disk spans roughly 50-60px. The same few
    pixels of edge-detection noise are a far larger *relative* error
    against the smaller reference, so this method should not be preferred
    over plate-rim calibration on this dataset despite the sharper edge.

    When multiple disks are detected, pass the median refined radius (from
    ``refine_disk_radius_px()``) to reduce the effect of any single outlier.

    Args:
        disk_radius_px: Detected radius of an antibiotic disk in pixels.
        disk_diameter_mm: Physical disk diameter in mm. Standard CLSI disks
            are 6.0 mm; change only for non-standard consumables.

    Returns:
        Calibration factor in pixels per millimetre.

    Raises:
        ValueError: If either argument is not strictly positive.
    """
    if disk_radius_px <= 0:
        raise ValueError(f"disk_radius_px must be positive, got {disk_radius_px}")
    if disk_diameter_mm <= 0:
        raise ValueError(f"disk_diameter_mm must be positive, got {disk_diameter_mm}")
    return (disk_radius_px * 2.0) / disk_diameter_mm


def refine_disk_radius_px(
    image: NDArray[np.uint8],
    disks: list[DiskResult],
) -> float:
    """Re-measure the median disk radius independently of the detector's own vote.

    ``disk.radius_px`` (from ``DiskDetector``) is not a reliable calibration
    reference on its own: when the caller's ``px_per_mm`` seed is itself
    plate-rim calibration, Hough's disk search window is derived directly
    from that same estimate (see ``detector.py::_hough_search_window``), so
    the reported radius is not an independent measurement -- it is
    plate-rim calibration scaled by whatever HoughCircles happens to vote
    for inside a window centred on that same estimate. Measured directly:
    the resulting "disk calibration" tracked plate-rim calibration at a
    near-constant ~0.80x ratio across 20 real photos -- far too tight and
    consistent to be an independent physical measurement, and a strong
    signal of the circular dependency itself, not of disk size.

    This function re-measures each detected disk's true edge locally
    instead: a small Otsu threshold in a tight crop around each disk finds
    the bright disk-vs-background boundary directly (the disk is small,
    round, and high-contrast, so this is a much easier and more local
    problem than global zone segmentation), independent of any calibration
    seed. The median across all detected disks is returned.

    Args:
        image: Full BGR plate image.
        disks: Detected disks (from ``DiskDetector.detect()``), used for
            their approximate centre and radius (the radius only seeds the
            crop size, not the result).

    Returns:
        Median refined disk radius in pixels. Falls back to the median of
        ``disk.radius_px`` if no disk's edge can be re-measured (e.g. every
        crop is degenerate).

    Raises:
        ValueError: If ``disks`` is empty.
    """
    if not disks:
        raise ValueError("disks must be non-empty to refine a calibration radius")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    refined = [
        r for d in disks
        if (r := _local_disk_edge_radius(gray, d.center_x, d.center_y, d.radius_px)) is not None
    ]
    if not refined:
        return float(np.median([d.radius_px for d in disks]))
    return float(np.median(refined))


def _local_disk_edge_radius(
    gray: NDArray[np.uint8],
    center_x: int,
    center_y: int,
    seed_radius_px: float,
) -> float | None:
    """Measure one disk's true edge via a local, calibration-independent Otsu threshold.

    Args:
        gray: Full-image grayscale array.
        center_x: Disk centre x, in full-image pixels.
        center_y: Disk centre y, in full-image pixels.
        seed_radius_px: Detector's own radius estimate, used only to size the
            local crop (generously, via ``_DISK_REFINE_MARGIN``) -- not
            trusted as the measurement itself.

    Returns:
        Refined radius in pixels, or ``None`` if no contour near the disk
        centre was found in the crop.
    """
    pad = max(1, int(seed_radius_px * _DISK_REFINE_MARGIN))
    y0, y1 = max(0, center_y - pad), min(gray.shape[0], center_y + pad)
    x0, x1 = max(0, center_x - pad), min(gray.shape[1], center_x + pad)
    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        return None
    blurred = cv2.GaussianBlur(roi, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    local_x, local_y = center_x - x0, center_y - y0
    best, best_dist_sq = None, float("inf")
    for c in contours:
        moments = cv2.moments(c)
        if moments["m00"] == 0:
            continue
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
        dist_sq = (cx - local_x) ** 2 + (cy - local_y) ** 2
        if dist_sq < best_dist_sq:
            best_dist_sq, best = dist_sq, c
    if best is None:
        return None
    (_, _), radius = cv2.minEnclosingCircle(best)
    return float(radius)


def detect_plate_circle(image: NDArray[np.uint8]) -> tuple[int, int, int] | None:
    """Detect the plate rim via Hough Circle Transform.

    Applies Gaussian blur to reduce noise, then searches for a circle whose
    radius spans 25-50% of the shorter image dimension (appropriate for a
    plate that fills most of the frame). The largest detected circle is
    taken as the plate rim.

    Args:
        image: Full BGR image array as returned by ``cv2.imread``.

    Returns:
        ``(center_x, center_y, radius)`` in pixels, or ``None`` if no
        circle was found.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (15, 15), 3)

    h, w = gray.shape
    min_radius = min(h, w) // 4
    max_radius = min(h, w) // 2

    circles = None
    for param2 in (40, 30, 20):
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.5,
            minDist=min(h, w),
            param1=80,
            param2=param2,
            minRadius=min_radius,
            maxRadius=max_radius,
        )
        if circles is not None:
            break

    if circles is None:
        return None
    circles = np.around(circles).astype(np.uint16)
    largest = max(circles[0], key=lambda c: c[2])
    return int(largest[0]), int(largest[1]), int(largest[2])


def calibrate_px_per_mm(
    image: NDArray[np.uint8],
    plate_diameter_mm: float = 90.0,
) -> tuple[float, float]:
    """Detect the plate rim and compute the pixel-to-millimetre ratio.

    Args:
        image: Full BGR image array as returned by ``cv2.imread``.
        plate_diameter_mm: Known physical diameter of the Petri dish in mm.
            Standard Mueller-Hinton plates measure 90 mm.

    Returns:
        A ``(plate_diameter_px, px_per_mm)`` tuple where:

        - ``plate_diameter_px`` is the pixel-space diameter of the detected
          plate (or the fallback estimate).
        - ``px_per_mm`` is the calibration ratio used by the segmenter to
          convert pixel measurements to millimetres.
    """
    circle = detect_plate_circle(image)
    if circle is not None:
        plate_diameter_px = float(circle[2]) * 2
    else:
        h, w = image.shape[:2]
        plate_diameter_px = float(min(h, w)) * _PLATE_FALLBACK_FRACTION

    px_per_mm = plate_diameter_px / plate_diameter_mm
    return plate_diameter_px, px_per_mm
