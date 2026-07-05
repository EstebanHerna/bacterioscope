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

import cv2
import numpy as np
from numpy.typing import NDArray


def calibrate_px_per_mm(
    image: NDArray[np.uint8],
    plate_diameter_mm: float = 90.0,
) -> tuple[float, float]:
    """Detect the plate rim and compute the pixel-to-millimetre ratio.

    Applies Gaussian blur to reduce noise, then runs the Hough Circle
    Transform searching for a circle whose radius spans 25–50 % of the
    shorter image dimension (appropriate for a plate that fills most of
    the frame).  The largest detected circle is taken as the plate rim.

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
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (15, 15), 3)

    h, w = gray.shape
    min_radius = min(h, w) // 4
    max_radius = min(h, w) // 2

    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.5,
        minDist=min(h, w),
        param1=80,
        param2=40,
        minRadius=min_radius,
        maxRadius=max_radius,
    )

    if circles is not None:
        circles = np.around(circles).astype(np.uint16)
        largest = max(circles[0], key=lambda c: c[2])
        plate_diameter_px = float(largest[2]) * 2
    else:
        plate_diameter_px = float(min(h, w)) * 0.9

    px_per_mm = plate_diameter_px / plate_diameter_mm
    return plate_diameter_px, px_per_mm
