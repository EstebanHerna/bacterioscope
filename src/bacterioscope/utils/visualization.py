"""Annotated image generation for BacterioScope analysis results.

What gets drawn
---------------
For every antibiotic disk detected on the plate this module draws:

- **Zone boundary** — the real segmented contour from the inhibition zone mask
  (or a circle fallback when no mask is available).
- **Disk circle** — the paper disk boundary, always drawn as a thin circle.
- **Text label** — antibiotic name, zone diameter in mm, and S/I/R category.
- **Flag ring** — an amber warning ring drawn outside the zone for disks that
  triggered one or more quality flags (low circularity, small zone, boundary
  contact, or overlap with another zone).

Colour coding (clinical convention)
------------------------------------
S (Susceptible): muted green — standard treatment likely effective.
I (Intermediate): muted amber — may work at higher dose or local site.
R (Resistant): muted red — antibiotic unlikely to be effective.
UNKNOWN: grey — no CLSI breakpoint found for this disk.
"""

from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.segmentation.watershed import ZoneResult

COLORS: dict[str, tuple[int, int, int]] = {
    "S": (80, 180, 70),          # muted green in BGR
    "I": (45, 150, 205),         # muted amber in BGR
    "R": (60, 60, 185),          # muted red in BGR
    "UNKNOWN": (110, 110, 110),
}

_FLAG_COLOR: tuple[int, int, int] = (45, 135, 200)   # amber-orange warning in BGR
_FLAG_RING_OFFSET: int = 6                             # pixels beyond zone radius

# A solid block stamped in the top-left corner of every annotated output.
# Lets the app detect and reject an already-annotated image re-uploaded as if
# it were a fresh photo -- feeding Hough circle detection an image full of
# drawn circles and text produces nonsense (hundreds of false-positive disks).
WATERMARK_COLOR: tuple[int, int, int] = (255, 0, 255)  # pure magenta in BGR
WATERMARK_SIZE_PX: int = 18
_WATERMARK_TOLERANCE: int = 45  # allows for JPEG compression drift at block edges


def _draw_zone_contour(
    image: NDArray[np.uint8],
    zone: ZoneResult,
    color: tuple[int, int, int],
    thickness: int = 2,
) -> None:
    """Draw the real segmented zone boundary, falling back to a circle.

    Uses the binary mask stored in ZoneResult to extract the actual contour
    produced by the watershed segmenter.  When the mask is unavailable,
    draws a circle with radius_px as a fallback.

    Args:
        image: BGR image array modified in place.
        zone: Zone measurement result containing the mask and centroid.
        color: BGR colour tuple for the contour.
        thickness: Line thickness in pixels.
    """
    if zone.mask is not None:
        contours, _ = cv2.findContours(zone.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            cv2.drawContours(image, contours, -1, color, thickness)
            return
    if zone.radius_px > 0:
        cv2.circle(image, (zone.center_x, zone.center_y), int(zone.radius_px), color, thickness)


def _draw_flag_ring(image: NDArray[np.uint8], zone: ZoneResult) -> None:
    """Draw an amber warning ring just outside a flagged zone.

    Args:
        image: BGR image array modified in place.
        zone: Zone whose measurement triggered one or more quality flags.
    """
    r = int(zone.radius_px) + _FLAG_RING_OFFSET
    if r > 0:
        cv2.circle(image, (zone.center_x, zone.center_y), r, _FLAG_COLOR, 2)


def draw_results(
    image: NDArray[np.uint8],
    disks: list[DiskResult],
    zones: list[ZoneResult],
    classifications: list[SusceptibilityResult],
    flags: list[list[str]] | None = None,
    stroke_color: tuple[int, int, int] | None = None,
) -> NDArray[np.uint8]:
    """Overlay detection and classification results on a plate image.

    Draws the real zone contour (from the segmentation mask when available),
    the disk circle, and a text label for each detected disk.  Disks with
    non-empty flags receive an additional amber warning ring drawn outside
    their zone boundary.

    Args:
        image: BGR image array to annotate. Pass a ``.copy()`` to preserve
            the original.
        disks: One DiskResult per detected disk (position and radius).
        zones: One ZoneResult per disk — contains the segmentation mask and
            zone measurements.
        classifications: One SusceptibilityResult per disk — S/I/R category
            and CLSI breakpoints used.
        flags: Optional list of flag lists, one per disk. Each inner list
            contains strings such as 'low_circularity', 'small_zone',
            'boundary', 'overlap'. Flagged disks receive an amber warning ring.
            Pass None or an empty list to draw no flags.
        stroke_color: When provided, overrides the S/I/R colour for all zone
            boundaries. Useful for uniform-colour overlay modes in the UI.
            Pass None to use the category colour (default).

    Returns:
        The annotated BGR image (same array that was passed in).
    """
    for idx, (disk, zone, cls) in enumerate(zip(disks, zones, classifications)):
        color = stroke_color if stroke_color is not None \
            else COLORS.get(cls.category, COLORS["UNKNOWN"])
        disk_flags = flags[idx] if flags is not None and idx < len(flags) else []

        if disk_flags:
            _draw_flag_ring(image, zone)

        _draw_zone_contour(image, zone, color)
        cv2.circle(image, (disk.center_x, disk.center_y), disk.radius_px, (210, 210, 210), 1)

        label = f"{cls.antibiotic}: {cls.zone_diameter_mm:.1f}mm ({cls.category})"
        cv2.putText(
            image, label,
            (disk.center_x - 60, disk.center_y - disk.radius_px - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA,
        )

    stamp_watermark(image)
    return image


def stamp_watermark(image: NDArray[np.uint8]) -> None:
    """Stamp a solid marker block in the top-left corner, in place.

    Marks this image as BacterioScope output so ``has_watermark()`` can
    reject it if it is later re-uploaded as if it were a fresh photo. Call
    this on any image saved for a human to look at that draws detection
    results onto a copy of an input photo -- not just ``draw_results()``'s
    own output (e.g. ``scripts/annotate_pairs.py``'s numbered disk overlay
    is exactly this kind of image and must be stamped too).
    """
    size = min(WATERMARK_SIZE_PX, image.shape[0], image.shape[1])
    if size > 0:
        image[0:size, 0:size] = WATERMARK_COLOR


def has_watermark(image: NDArray[np.uint8]) -> bool:
    """Check whether an image carries the BacterioScope output watermark.

    Args:
        image: BGR image array, any size.

    Returns:
        ``True`` if the top-left corner matches ``WATERMARK_COLOR`` within
        ``_WATERMARK_TOLERANCE`` (accounts for JPEG recompression), meaning
        this image is already an annotated pipeline output and must not be
        re-analyzed as a fresh photograph.
    """
    size = min(WATERMARK_SIZE_PX, image.shape[0], image.shape[1])
    if size <= 0:
        return False
    corner = image[0:size, 0:size].reshape(-1, 3).astype(np.int16)
    target = np.array(WATERMARK_COLOR, dtype=np.int16)
    diff = np.abs(corner - target).max(axis=1)
    return bool(np.mean(diff <= _WATERMARK_TOLERANCE) > 0.95)
