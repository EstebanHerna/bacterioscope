from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray


def calibrate_px_per_mm(
    image: NDArray[np.uint8],
    plate_diameter_mm: float = 90.0,
) -> tuple[float, float]:
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
