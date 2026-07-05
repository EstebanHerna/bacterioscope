"""Inhibition zone segmentation and measurement for antibiotic disks.

Clinical background
-------------------
When a paper antibiotic disk is placed on an agar plate seeded with bacteria
and incubated overnight, susceptible bacteria cannot grow near the disk.  The
resulting clear circular area is the **inhibition zone**.  Its diameter (in mm)
is what clinicians compare against CLSI breakpoint tables to determine whether
a pathogen is Susceptible, Intermediate, or Resistant to that antibiotic.

What this module does
---------------------
Given the full plate image and the pixel coordinates and size of one disk
(from ``detector.py``), the segmenter:

1. **Crops a region of interest (ROI)** centred on the disk.  The crop
   extends ``margin_factor × disk_radius`` pixels in each direction so it
   covers the expected zone area.
2. **Converts to grayscale and blurs** with a Gaussian kernel to suppress
   sensor noise.
3. **Applies Otsu thresholding** — an algorithm that automatically selects the
   brightness level that best separates the bright inhibition zone (clear agar)
   from the darker bacterial lawn.
4. **Morphological cleanup**: closing fills small holes in the mask; opening
   removes isolated speckles.
5. **Finds contours** — the outlines of white regions in the binary mask.
   The contour whose centroid is closest to the disk centre is chosen as the
   inhibition zone.
6. **Fits a minimum enclosing circle** to the chosen contour and converts its
   radius from pixels to millimetres using the ``px_per_mm`` calibration
   factor.

Name note
---------
The module is named ``watershed`` because an earlier prototype used OpenCV's
watershed segmentation algorithm.  The current implementation uses the simpler
and more robust Otsu + contour approach, but the module name was kept for
continuity.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from bacterioscope.detection.detector import DiskResult


@dataclass
class ZoneResult:
    """Measurements for the inhibition zone surrounding one antibiotic disk.

    All pixel coordinates are relative to the full plate image (not the
    cropped ROI).  The ``diameter_mm`` field is the clinically relevant value
    compared against CLSI breakpoints for S/I/R classification.

    Attributes:
        disk_label: Label of the disk this zone belongs to.  Matches
            ``DiskResult.label`` (e.g. ``'ciprofloxacin'`` or ``'disk_0'``).
        center_x: Horizontal pixel coordinate of the zone centre.
        center_y: Vertical pixel coordinate of the zone centre.
        radius_px: Radius of the minimum enclosing circle in pixels.
        diameter_px: Zone diameter in pixels (``2 × radius_px``).
        diameter_mm: Zone diameter in millimetres.  This is the value reported
            to the clinician and compared against CLSI breakpoints.
        area_px: Area of the segmented zone contour in square pixels.
        circularity: How circular the zone is.  ``1.0`` = perfect circle;
            lower values indicate an irregular or asymmetric zone, which may
            signal measurement uncertainty.
        mask: Binary image the same size as the plate where ``255`` marks the
            zone interior.  Used by ``draw_results()`` for visualization.
            ``None`` if no zone was found.
    """
    disk_label: str
    center_x: int
    center_y: int
    radius_px: float
    diameter_px: float
    diameter_mm: float
    area_px: float
    circularity: float
    mask: NDArray[np.uint8] | None = None


class ZoneSegmenter:
    """Segments and measures the inhibition zone for one antibiotic disk.

    Call ``segment()`` once per detected disk.  The segmenter is stateless
    and thread-safe; a single instance can process many disks concurrently.

    Attributes:
        margin_factor: How far beyond the disk radius (as a multiple of
            ``disk.radius_px``) to extend the search crop.  The default of
            ``4.0`` means the ROI extends 4 × disk_radius pixels in each
            direction, covering zones up to 8 × disk_radius in diameter.
            Increase for plates with very large inhibition zones.
    """
    def __init__(self, margin_factor: float = 4.0) -> None:
        self.margin_factor = margin_factor

    def segment(
        self,
        image: NDArray[np.uint8],
        disk: DiskResult,
        px_per_mm: float,
    ) -> ZoneResult:
        """Measure the inhibition zone diameter for one antibiotic disk.

        Args:
            image: Full BGR plate image.  Only a crop around ``disk`` is
                processed; the rest of the image is untouched.
            disk: Detection result for the disk to measure.  Provides the
                centre coordinates and radius used to define the search area.
            px_per_mm: Calibration factor from ``calibrate_px_per_mm()``.
                Used to convert the pixel-space radius to millimetres.

        Returns:
            ``ZoneResult`` containing the zone diameter in both pixels and mm.
            If no zone contour is found (empty plate region, very resistant
            organism with no inhibition), returns a ``ZoneResult`` with all
            numerical fields set to zero.
        """
        search_radius = int(disk.radius_px * self.margin_factor)
        roi, offset_x, offset_y = self._extract_roi(image, disk, search_radius)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        _, binary = cv2.threshold(
            blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return self._no_zone(disk, px_per_mm)

        disk_local_x = disk.center_x - offset_x
        disk_local_y = disk.center_y - offset_y

        best_contour = self._find_zone_contour(contours, disk_local_x, disk_local_y)
        if best_contour is None:
            return self._no_zone(disk, px_per_mm)

        area = cv2.contourArea(best_contour)
        perimeter = cv2.arcLength(best_contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0

        (cx, cy), radius = cv2.minEnclosingCircle(best_contour)
        diameter_px = radius * 2
        diameter_mm = diameter_px / px_per_mm

        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        shifted_contour = best_contour + np.array([offset_x, offset_y])
        cv2.drawContours(mask, [shifted_contour], -1, 255, -1)

        return ZoneResult(
            disk_label=disk.label,
            center_x=int(cx) + offset_x,
            center_y=int(cy) + offset_y,
            radius_px=float(radius),
            diameter_px=float(diameter_px),
            diameter_mm=float(diameter_mm),
            area_px=float(area),
            circularity=float(circularity),
            mask=mask,
        )

    def _extract_roi(
        self,
        image: NDArray[np.uint8],
        disk: DiskResult,
        search_radius: int,
    ) -> tuple[NDArray[np.uint8], int, int]:
        """Crop a square region of interest around a disk, clamped to image bounds.

        Returns:
            ``(roi, offset_x, offset_y)`` where ``offset_x`` and ``offset_y``
            are the pixel coordinates of the top-left corner of the crop
            within the full image.  Add these offsets to any pixel coordinate
            measured inside the ROI to get full-image coordinates.
        """
        h, w = image.shape[:2]
        x1 = max(0, disk.center_x - search_radius)
        y1 = max(0, disk.center_y - search_radius)
        x2 = min(w, disk.center_x + search_radius)
        y2 = min(h, disk.center_y + search_radius)
        return image[y1:y2, x1:x2], x1, y1

    def _find_zone_contour(
        self,
        contours: Sequence[Any],
        disk_x: int,
        disk_y: int,
    ) -> NDArray[np.uint8] | None:
        """Return the contour whose centroid is closest to the disk centre.

        Iterates over all contours from the thresholded ROI and selects the
        one most likely to represent the inhibition zone (i.e. the one
        centred on the disk, not a background blob).

        Args:
            contours: List of contours from ``cv2.findContours``.
            disk_x: Disk centre x coordinate in ROI-local pixels.
            disk_y: Disk centre y coordinate in ROI-local pixels.

        Returns:
            The best contour array, or ``None`` if all contours have zero area.
        """
        best: NDArray[np.uint8] | None = None
        best_dist = float("inf")
        for c in contours:
            moments = cv2.moments(c)
            if moments["m00"] == 0:
                continue
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])
            dist = np.sqrt((cx - disk_x) ** 2 + (cy - disk_y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = c
        return best

    def _no_zone(self, disk: DiskResult, px_per_mm: float) -> ZoneResult:
        """Return a zero-measurement ZoneResult when no zone contour is found."""
        return ZoneResult(
            disk_label=disk.label,
            center_x=disk.center_x,
            center_y=disk.center_y,
            radius_px=0.0,
            diameter_px=0.0,
            diameter_mm=0.0,
            area_px=0.0,
            circularity=0.0,
            mask=None,
        )
