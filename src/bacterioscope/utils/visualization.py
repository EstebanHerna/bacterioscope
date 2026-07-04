from __future__ import annotations

import cv2
import numpy as np
from numpy.typing import NDArray

from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.detection.detector import DiskResult
from bacterioscope.segmentation.watershed import ZoneResult

COLORS = {
    "S": (0, 200, 0),
    "I": (0, 200, 255),
    "R": (0, 0, 220),
    "UNKNOWN": (128, 128, 128),
}


def draw_results(
    image: NDArray[np.uint8],
    disks: list[DiskResult],
    zones: list[ZoneResult],
    classifications: list[SusceptibilityResult],
) -> NDArray[np.uint8]:
    for disk, zone, cls in zip(disks, zones, classifications):
        color = COLORS.get(cls.category, COLORS["UNKNOWN"])

        if zone.radius_px > 0:
            cv2.circle(
                image,
                (zone.center_x, zone.center_y),
                int(zone.radius_px),
                color,
                2,
            )

        cv2.circle(image, (disk.center_x, disk.center_y), disk.radius_px, (255, 255, 255), 2)

        label = f"{cls.antibiotic}: {cls.zone_diameter_mm:.1f}mm ({cls.category})"
        label_y = disk.center_y - disk.radius_px - 10
        cv2.putText(
            image,
            label,
            (disk.center_x - 60, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    return image
