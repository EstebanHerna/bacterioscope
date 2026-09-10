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
   covers the expected zone area (bounded by two geometric caps -- see
   ``_search_radius()``).
2. **Converts to grayscale and blurs** with a Gaussian kernel to suppress
   sensor noise.
3. **Applies Otsu thresholding with the disk itself excluded** from the
   histogram (see ``_otsu_excluding_disk()``) — an algorithm that
   automatically selects the brightness level that best separates the
   inhibition zone (clear agar, reads darker under reflected light in this
   dataset) from the brighter, cloudier bacterial lawn. The disk is excluded
   because it is almost always a much stronger bright/dark signal than the
   zone-vs-lawn contrast that actually matters (sometimes as little as 15
   grey levels on real photos) -- left in, Otsu reliably locks onto
   disk-vs-everything instead of zone-vs-lawn, and the resulting mask fills
   nearly the entire crop rather than tracing the true, much smaller
   boundary. Confirmed to matter on real UZH photos: identity-matched
   accuracy on the 20-image reference set moved from EA=24.1%/MAE=7.44mm to
   EA=32.9%/MAE=6.28mm with this fix alone.
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

_GAUSS_KERNEL: tuple[int, int] = (5, 5)
_MORPH_KERNEL: tuple[int, int] = (5, 5)
_CLOSE_ITERS: int = 2
_OPEN_ITERS: int = 1
_CLAHE_CLIP_LIMIT: float = 2.0
_CLAHE_TILE_SIZE: tuple[int, int] = (8, 8)

# Multiple of disk.radius_px excluded from the Otsu histogram (see
# _otsu_excluding_disk()) -- generous enough to cover the disk's own edge
# blur after Gaussian smoothing.
_DISK_EXCLUSION_MARGIN: float = 1.3

# CLSI zone diameters reported in clinical practice essentially never exceed
# this, even for the most susceptible organism-antibiotic combinations. Used
# as a hard ceiling on the search crop so a sparse plate (no nearby disk to
# cap against) cannot grow the ROI past the point where Otsu starts picking
# up the petri dish rim or background instead of the true zone edge.
_MAX_PLAUSIBLE_ZONE_RADIUS_MM: float = 15.0


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
            ``disk.radius_px``) the search crop extends, before the two caps
            in ``_search_radius()`` apply (nearest-neighbour distance, and
            an absolute plausible-zone-size ceiling). ``4.0`` is a
            deliberate compromise, not a tuned optimum: raising it to give
            large real zones more room was tried and measured directly on
            real photos -- it does not fix them. Every disk's zone mask
            already fills 100% of its crop's bounding box at ``4.0``
            (confirmed on real UZH photos, including sparse 4-disk plates
            with no nearby neighbour to blame), and raising the factor to
            5.0-8.0 does not shrink that fill ratio -- Otsu keeps marking
            the entire crop as zone regardless of crop size on these
            specific images, then ``cv2.minEnclosingCircle`` on a
            fully-filled square reports an even larger, more implausible
            diameter (confirmed: some real photos jumped to 45-50mm on a
            physically ~90mm plate). This means the failure on these images
            is Otsu not finding a true zone-vs-lawn boundary at all, not a
            crop that is merely too small -- a deeper problem than crop
            size, not fixed by this class. ``4.0`` was kept because it
            bounds the resulting error to a smaller number when Otsu fails,
            rather than a larger one.
        use_clahe: When ``True``, apply Contrast Limited Adaptive Histogram
            Equalization (CLAHE) to the grayscale ROI before Otsu thresholding.
            Not exposed through ``PipelineConfig``, the CLI, or the Streamlit
            demo -- nothing in the running pipeline enables this today, by
            design: measured directly on the 20-image identity-matched
            real-photo set, it makes measurements worse, not better (EA
            32.9%->24.7%, MAE 6.28mm->7.29mm), contrary to the theoretical
            expectation that local contrast enhancement should help uneven
            lighting. Keep ``False`` unless a future dataset shows otherwise.
    """
    def __init__(self, margin_factor: float = 4.0, use_clahe: bool = False) -> None:
        self.margin_factor = margin_factor
        self.use_clahe = use_clahe
        self._clahe = cv2.createCLAHE(clipLimit=_CLAHE_CLIP_LIMIT, tileGridSize=_CLAHE_TILE_SIZE)

    def _search_radius(
        self,
        disk: DiskResult,
        px_per_mm: float,
        neighbors: Sequence[DiskResult] = (),
    ) -> int:
        """Compute the ROI half-size for one disk, geometrically bounded.

        Two independent, defensive caps on ``margin_factor * disk.radius_px``:
        never reach past half the distance to the nearest other disk centre
        (so a larger margin_factor, if ever raised, cannot bleed into a
        neighbour's zone), and never exceed ``_MAX_PLAUSIBLE_ZONE_RADIUS_MM``
        converted to pixels (so it cannot grow large enough for Otsu to pick
        up the petri dish rim or background instead of a zone edge -- this
        was directly observed on real 4-disk, widely-spaced plates once
        raised past this size, where measured diameters jumped to 45-50mm on
        what is physically a ~90mm plate). At the current default
        ``margin_factor=4.0`` neither cap binds on any image tested; both
        exist as guardrails for if/when a future fix increases the base
        margin again -- raising it alone was tried and did not fix the
        underlying issue (see ``margin_factor`` docstring above).

        Args:
            disk: The disk being measured.
            px_per_mm: Calibration factor, used to convert the absolute
                plausible-zone-size cap from millimetres to pixels.
            neighbors: Every other disk on the same plate (excluding
                ``disk`` itself). Pass an empty sequence for a single
                isolated disk.

        Returns:
            Half-width of the square ROI to crop, in pixels.
        """
        uncapped = disk.radius_px * self.margin_factor
        absolute_cap = _MAX_PLAUSIBLE_ZONE_RADIUS_MM * px_per_mm
        capped = min(uncapped, absolute_cap)
        if not neighbors:
            return int(capped)
        nearest_dist = min(
            np.hypot(disk.center_x - n.center_x, disk.center_y - n.center_y)
            for n in neighbors
        )
        return int(min(capped, max(nearest_dist / 2, disk.radius_px)))

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
        search_radius = self._search_radius(disk, px_per_mm)
        roi, offset_x, offset_y = self._extract_roi(image, disk, search_radius)

        blurred = self._preprocess_roi(roi)
        disk_local_x = disk.center_x - offset_x
        disk_local_y = disk.center_y - offset_y
        binary = self._otsu_excluding_disk(blurred, disk_local_x, disk_local_y, disk.radius_px)
        binary = self._apply_morphology(binary)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return self._no_zone(disk, px_per_mm)

        best_contour = self._find_zone_contour(contours, disk_local_x, disk_local_y)
        if best_contour is None:
            return self._no_zone(disk, px_per_mm)

        return self._build_zone_result(image, disk, best_contour, offset_x, offset_y, px_per_mm)

    def _otsu_excluding_disk(
        self,
        blurred: NDArray[np.uint8],
        disk_local_x: int,
        disk_local_y: int,
        disk_radius_px: float,
    ) -> NDArray[np.uint8]:
        """Threshold a ROI with the disk itself excluded from Otsu's histogram.

        The paper disk (bright white, ~150-200) is almost always a much
        stronger bimodal signal than the zone-vs-lawn contrast that actually
        matters (often as little as 15-20 grey levels apart on real photos).
        Left in the histogram, Otsu reliably locks onto disk-vs-everything
        instead -- confirmed directly: a between-class-variance quality
        score computed the same way Otsu picks its threshold was *highest*
        (0.91-0.92) on exactly the real photos whose zone masks filled 100%
        of their crop's bounding box, because that score was measuring the
        disk/background split, not the zone/lawn one. Masking the disk out
        before computing the threshold removes that false signal so Otsu
        sees only the zone-vs-lawn contrast that is actually being measured.

        Args:
            blurred: Grayscale, Gaussian-blurred ROI.
            disk_local_x: Disk centre x coordinate in ROI-local pixels.
            disk_local_y: Disk centre y coordinate in ROI-local pixels.
            disk_radius_px: Disk radius in pixels (full-image scale; the ROI
                is not resized, so this applies directly).

        Returns:
            Binary mask (``255`` = zone candidate) with the disk's own area
            excluded, before morphological cleanup.
        """
        h, w = blurred.shape
        outside_disk = np.full((h, w), 255, dtype=np.uint8)
        exclusion_radius = int(disk_radius_px * _DISK_EXCLUSION_MARGIN)
        cx = min(max(disk_local_x, 0), w - 1)
        cy = min(max(disk_local_y, 0), h - 1)
        cv2.circle(outside_disk, (cx, cy), exclusion_radius, 0, -1)

        sample = blurred[outside_disk > 0]
        if sample.size == 0:
            thresh_val, _ = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            thresh_val, _ = cv2.threshold(
                sample.reshape(-1, 1), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
            )
        _, binary = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)
        return cv2.bitwise_and(binary, outside_disk)

    def segment_all(
        self,
        image: NDArray[np.uint8],
        disks: list[DiskResult],
        px_per_mm: float,
    ) -> list[ZoneResult]:
        """Measure inhibition zones for every disk on a plate jointly.

        Uses exactly the same isolated-ROI Otsu thresholding as ``segment()``
        (proven correct: measures known-27mm synthetic zones to within
        ~3mm), with one addition -- before contour-picking, the ROI's binary
        mask is restricted to this disk's own **Voronoi cell**: the region
        geometrically closer to this disk's centre than to any other
        detected disk. On an isolated disk this restriction changes nothing
        (its own ROI never reaches a neighbour). On a plate with
        closely-spaced or confluent disks, it stops the ROI from picking up
        a neighbour's zone that has merged into this one -- the boundary
        between two confluent zones falls on the perpendicular bisector
        between their disk centres, independent of image noise (whole-plate
        thresholding and intensity/distance-transform watershed were tried
        first and discarded here: a plate-wide Otsu histogram gets dominated
        by the much stronger plate-vs-background contrast rather than the
        zone-vs-lawn contrast that matters, and gradient-based watershed
        picks up agar texture and printed labels as false ridges).

        Falls back to independent ``segment()`` calls when there are 0 or 1
        disks, where confluence with a neighbour is not possible.

        Args:
            image: Full BGR plate image.
            disks: All disks detected on this plate, in pipeline order.
            px_per_mm: Calibration factor for pixel-to-mm conversion.

        Returns:
            List of ZoneResult objects, one per disk, in the same order as
            ``disks``.
        """
        if len(disks) <= 1:
            return [self.segment(image, d, px_per_mm) for d in disks]
        return [
            self._segment_within_voronoi_cell(image, disks, idx, px_per_mm)
            for idx in range(len(disks))
        ]

    def _segment_within_voronoi_cell(
        self,
        image: NDArray[np.uint8],
        disks: list[DiskResult],
        idx: int,
        px_per_mm: float,
    ) -> ZoneResult:
        """Segment one disk's own isolated ROI, restricted to its Voronoi cell.

        Args:
            image: Full BGR plate image.
            disks: All disks on the plate (needed to compute the Voronoi
                cell boundary against every neighbour, not just this disk).
            idx: Index into ``disks`` of the disk being measured.
            px_per_mm: Calibration factor for pixel-to-mm conversion.

        Returns:
            ZoneResult for ``disks[idx]``.
        """
        disk = disks[idx]
        neighbors = [d for i, d in enumerate(disks) if i != idx]
        search_radius = self._search_radius(disk, px_per_mm, neighbors)
        roi, offset_x, offset_y = self._extract_roi(image, disk, search_radius)

        blurred = self._preprocess_roi(roi)
        disk_local_x = disk.center_x - offset_x
        disk_local_y = disk.center_y - offset_y
        binary = self._otsu_excluding_disk(blurred, disk_local_x, disk_local_y, disk.radius_px)
        binary = self._apply_morphology(binary)

        local_disks = [
            (d.center_x - offset_x, d.center_y - offset_y) for d in disks
        ]
        nearest = self._nearest_disk_map(local_disks, roi.shape[:2])
        cell = (nearest == idx).astype(np.uint8) * 255
        binary = cv2.bitwise_and(binary, cell)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return self._no_zone(disk, px_per_mm)

        best_contour = self._find_zone_contour(contours, disk_local_x, disk_local_y)
        if best_contour is None:
            return self._no_zone(disk, px_per_mm)

        return self._build_zone_result(image, disk, best_contour, offset_x, offset_y, px_per_mm)

    def _nearest_disk_map(
        self,
        centers: list[tuple[int, int]],
        shape: tuple[int, int],
    ) -> NDArray[np.intp]:
        """Assign every pixel to its geometrically nearest disk centre.

        A Voronoi tessellation seeded at the given centres: pixel
        ``(x, y)`` is assigned index ``i`` when ``centers[i]`` is the
        closest of all centres to that pixel by Euclidean distance.

        Args:
            centers: ``(x, y)`` pixel coordinates of every disk centre, in
                the same coordinate space as ``shape``.
            shape: ``(height, width)`` of the image to build the map over.

        Returns:
            Integer array of shape ``shape`` where each entry is the index
            into ``centers`` of the nearest centre to that pixel.
        """
        h, w = shape
        yy, xx = np.mgrid[0:h, 0:w]
        dist_sq_stack = np.stack([
            (xx - cx) ** 2 + (yy - cy) ** 2 for cx, cy in centers
        ])
        return np.argmin(dist_sq_stack, axis=0)

    def _preprocess_roi(self, roi: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Convert ROI to grayscale, optionally apply CLAHE, then Gaussian blur.

        Args:
            roi: BGR crop around one disk.

        Returns:
            Blurred grayscale image ready for Otsu thresholding.
        """
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        if self.use_clahe:
            gray = self._clahe.apply(gray)
        return cv2.GaussianBlur(gray, _GAUSS_KERNEL, 0)

    def _apply_morphology(self, binary: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Close small holes then remove isolated speckles from a binary mask.

        Args:
            binary: Thresholded binary image.

        Returns:
            Cleaned binary image after morphological close and open.
        """
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, _MORPH_KERNEL)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=_CLOSE_ITERS)
        return cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=_OPEN_ITERS)

    def _build_zone_result(
        self,
        image: NDArray[np.uint8],
        disk: DiskResult,
        contour: NDArray[np.uint8],
        offset_x: int,
        offset_y: int,
        px_per_mm: float,
    ) -> ZoneResult:
        """Measure a contour and construct the ZoneResult for the matched disk.

        Args:
            image: Full plate image (used only for its shape to build the mask).
            disk: Disk whose zone this contour represents.
            contour: Best zone contour in ROI-local coordinates.
            offset_x: X offset of the ROI top-left corner in the full image.
            offset_y: Y offset of the ROI top-left corner in the full image.
            px_per_mm: Calibration factor for pixel-to-mm conversion.

        Returns:
            ZoneResult with diameter, circularity, and zone mask.
        """
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0

        (cx, cy), radius = cv2.minEnclosingCircle(contour)
        diameter_px = radius * 2
        diameter_mm = diameter_px / px_per_mm

        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        shifted = contour + np.array([offset_x, offset_y])
        cv2.drawContours(mask, [shifted], -1, 255, -1)

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
