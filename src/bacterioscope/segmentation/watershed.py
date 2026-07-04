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
    def __init__(self, margin_factor: float = 4.0) -> None:
        self.margin_factor = margin_factor

    def segment(
        self,
        image: NDArray[np.uint8],
        disk: DiskResult,
        px_per_mm: float,
    ) -> ZoneResult:
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
