"""Annotated image generation for BacterioScope analysis results.

This module draws detection and classification output on top of the original
plate photograph to produce the visual report shown in the Streamlit demo and
saved by the CLI with the ``--output`` flag.

What gets drawn
---------------
For every antibiotic disk detected on the plate this module draws:

- **Outer coloured circle** — the boundary of the segmented inhibition zone.
- **Inner white circle** — the boundary of the paper antibiotic disk itself.
- **Text label** — antibiotic name, measured zone diameter, and S/I/R category,
  positioned above the disk.

Colour coding (clinical convention)
------------------------------------
================  =========  =====================================
Category          Colour     Meaning
================  =========  =====================================
S (Susceptible)   Green      Standard treatment likely effective.
I (Intermediate)  Amber      May work with higher dose / local use.
R (Resistant)     Red        Antibiotic unlikely to be effective.
UNKNOWN           Grey       No CLSI breakpoint found for this disk.
================  =========  =====================================
"""

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
    """Overlay detection and classification results on a plate image.

    Iterates over the parallel ``disks``, ``zones``, and ``classifications``
    lists and draws three elements per disk: the zone circle, the disk circle,
    and a text label.  Modifies ``image`` in place and also returns it.

    Args:
        image: BGR image array to annotate.  Pass a ``.copy()`` if you need
            to preserve the original unmodified.
        disks: One ``DiskResult`` per detected disk (position and size).
        zones: One ``ZoneResult`` per disk — contains the segmented zone
            radius in pixels and the measured diameter in mm.
        classifications: One ``SusceptibilityResult`` per disk — contains the
            antibiotic name, zone diameter, and S/I/R category.

    Returns:
        The annotated BGR image (the same array that was passed in).
    """
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
