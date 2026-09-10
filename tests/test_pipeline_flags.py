"""Tests for BacterioScopePipeline._compute_flags()."""

from __future__ import annotations

import numpy as np
import pytest

from bacterioscope.detection.detector import DiskResult
from bacterioscope.pipeline import BacterioScopePipeline
from bacterioscope.segmentation.watershed import ZoneResult


def _disk(cx: int = 100, cy: int = 100, r: int = 15) -> DiskResult:
    return DiskResult(
        label="ciprofloxacin", center_x=cx, center_y=cy, radius_px=r,
        confidence=1.0, bbox=(cx - r, cy - r, cx + r, cy + r),
    )


def _zone(
    cx: int = 100, cy: int = 100, r: float = 40.0,
    mm: float = 26.0, circularity: float = 0.95,
) -> ZoneResult:
    return ZoneResult(
        disk_label="ciprofloxacin", center_x=cx, center_y=cy,
        radius_px=r, diameter_px=r * 2, diameter_mm=mm,
        area_px=np.pi * r ** 2, circularity=circularity,
    )


@pytest.fixture
def pipeline() -> BacterioScopePipeline:
    return BacterioScopePipeline()


class TestComputeFlagsQuality:
    def test_no_flags_for_good_zone(self, pipeline: BacterioScopePipeline) -> None:
        flags = pipeline._compute_flags([_disk()], [_zone()], (500, 500, 3))
        assert flags == [[]]

    def test_flag_low_circularity(self, pipeline: BacterioScopePipeline) -> None:
        flags = pipeline._compute_flags([_disk()], [_zone(circularity=0.5)], (500, 500, 3))
        assert "low_circularity" in flags[0]

    def test_no_flag_when_diameter_zero(self, pipeline: BacterioScopePipeline) -> None:
        flags = pipeline._compute_flags([_disk()], [_zone(mm=0.0, circularity=0.0)], (500, 500, 3))
        assert "low_circularity" not in flags[0]

    def test_flag_small_zone(self, pipeline: BacterioScopePipeline) -> None:
        flags = pipeline._compute_flags([_disk()], [_zone(mm=4.0)], (500, 500, 3))
        assert "small_zone" in flags[0]

    def test_no_small_zone_flag_when_exactly_6mm(self, pipeline: BacterioScopePipeline) -> None:
        flags = pipeline._compute_flags([_disk()], [_zone(mm=6.0)], (500, 500, 3))
        assert "small_zone" not in flags[0]

    def test_no_small_zone_flag_when_zero(self, pipeline: BacterioScopePipeline) -> None:
        flags = pipeline._compute_flags([_disk()], [_zone(mm=0.0, r=0.0)], (500, 500, 3))
        assert "small_zone" not in flags[0]


class TestComputeFlagsBoundary:
    """A tolerance of _BOUNDARY_TOLERANCE_PX (15px) applies before flagging.

    Added after a 20-image real-photo audit found a zero-tolerance check
    flagged 45% of disks with a median overshoot of only 12px on a ~1024px
    image -- ordinary fitted-circle rounding noise on a dense grid, not a
    genuinely truncated measurement. Overshoots that matter (seen up to
    75px in the same audit) still flag under the tolerance.
    """

    def test_flag_boundary_zone_well_past_left_edge(self, pipeline: BacterioScopePipeline) -> None:
        zone = _zone(cx=10, cy=100, r=40.0)  # left edge at -30, overshoot 30
        flags = pipeline._compute_flags([_disk(cx=10)], [zone], (300, 300, 3))
        assert "boundary" in flags[0]

    def test_flag_boundary_zone_well_past_right_edge(self, pipeline: BacterioScopePipeline) -> None:
        zone = _zone(cx=290, cy=100, r=40.0)  # right edge at 330, overshoot 30
        flags = pipeline._compute_flags([_disk(cx=290)], [zone], (300, 300, 3))
        assert "boundary" in flags[0]

    def test_no_boundary_flag_for_centred_zone(self, pipeline: BacterioScopePipeline) -> None:
        zone = _zone(cx=150, cy=150, r=40.0)
        flags = pipeline._compute_flags([_disk(cx=150, cy=150)], [zone], (400, 400, 3))
        assert "boundary" not in flags[0]

    def test_small_overshoot_within_tolerance_not_flagged(
        self, pipeline: BacterioScopePipeline,
    ) -> None:
        zone = _zone(cx=30, cy=100, r=40.0)  # left edge at -10, overshoot 10 (< 15px tolerance)
        flags = pipeline._compute_flags([_disk(cx=30)], [zone], (300, 300, 3))
        assert "boundary" not in flags[0]

    def test_overshoot_exactly_at_tolerance_not_flagged(
        self, pipeline: BacterioScopePipeline,
    ) -> None:
        zone = _zone(cx=25, cy=100, r=40.0)  # left edge at -15, overshoot 15 (== tolerance)
        flags = pipeline._compute_flags([_disk(cx=25)], [zone], (300, 300, 3))
        assert "boundary" not in flags[0]

    def test_overshoot_one_past_tolerance_flagged(
        self, pipeline: BacterioScopePipeline,
    ) -> None:
        zone = _zone(cx=24, cy=100, r=40.0)  # left edge at -16, overshoot 16 (> tolerance)
        flags = pipeline._compute_flags([_disk(cx=24)], [zone], (300, 300, 3))
        assert "boundary" in flags[0]


class TestComputeFlagsOverlap:
    def test_flag_overlap_for_close_disks(self, pipeline: BacterioScopePipeline) -> None:
        d1, d2 = _disk(cx=100, cy=100), _disk(cx=130, cy=100)
        z1, z2 = _zone(cx=100, cy=100, r=40.0), _zone(cx=130, cy=100, r=40.0)
        flags = pipeline._compute_flags([d1, d2], [z1, z2], (400, 400, 3))
        assert "overlap" in flags[0]
        assert "overlap" in flags[1]

    def test_no_overlap_for_separated_disks(self, pipeline: BacterioScopePipeline) -> None:
        d1, d2 = _disk(cx=50, cy=50), _disk(cx=250, cy=250)
        z1, z2 = _zone(cx=50, cy=50, r=30.0), _zone(cx=250, cy=250, r=30.0)
        flags = pipeline._compute_flags([d1, d2], [z1, z2], (400, 400, 3))
        assert "overlap" not in flags[0]
        assert "overlap" not in flags[1]

    def test_overlap_not_duplicated(self, pipeline: BacterioScopePipeline) -> None:
        d1, d2 = _disk(cx=100, cy=100), _disk(cx=120, cy=100)
        z1, z2 = _zone(cx=100, cy=100, r=40.0), _zone(cx=120, cy=100, r=40.0)
        flags = pipeline._compute_flags([d1, d2], [z1, z2], (400, 400, 3))
        assert flags[0].count("overlap") == 1
        assert flags[1].count("overlap") == 1

    def test_no_disks_returns_empty(self, pipeline: BacterioScopePipeline) -> None:
        flags = pipeline._compute_flags([], [], (400, 400, 3))
        assert flags == []
