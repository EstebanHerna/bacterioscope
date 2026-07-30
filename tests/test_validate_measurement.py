"""Tests for rank-order diameter matching and Essential Agreement computation.

Uses synthetic diameter data to verify matching logic without requiring the
Dryad/UZH dataset to be present on the machine running tests.

Why only measurement accuracy is tested here:
    The Dryad/UZH reference uses EUCAST 2023 breakpoints; BacterioScope
    classifies with CLSI M100-Ed33 2023.  These standards differ for many
    antibiotic-organism combinations, so comparing S/I/R across them would
    produce misleading discordance rates.  Phase 0 therefore validates only
    zone-diameter measurement accuracy (mm), not S/I/R classification.
"""

from __future__ import annotations

import pytest

from bacterioscope.evaluation.metrics import essential_agreement, match_diameters_by_rank


class TestMatchDiametersByRank:
    def test_returns_ascending_pairs(self) -> None:
        measured = [30.0, 10.0, 20.0]
        reference = [28.0, 12.0, 22.0]
        pairs = match_diameters_by_rank(measured, reference)
        assert pairs == [(10.0, 12.0), (20.0, 22.0), (30.0, 28.0)]

    def test_already_sorted_unchanged(self) -> None:
        measured = [10.0, 20.0, 30.0]
        reference = [11.0, 21.0, 29.0]
        pairs = match_diameters_by_rank(measured, reference)
        assert pairs == [(10.0, 11.0), (20.0, 21.0), (30.0, 29.0)]

    def test_single_pair(self) -> None:
        assert match_diameters_by_rank([25.0], [26.0]) == [(25.0, 26.0)]

    def test_empty_lists(self) -> None:
        assert match_diameters_by_rank([], []) == []

    def test_equal_diameters(self) -> None:
        pairs = match_diameters_by_rank([20.0, 20.0], [20.0, 20.0])
        assert pairs == [(20.0, 20.0), (20.0, 20.0)]


class TestEAWithSyntheticData:
    def test_all_within_two_mm(self) -> None:
        measured = [25.0, 30.0, 18.0, 22.0]
        reference = [26.0, 29.0, 17.0, 21.0]
        assert essential_agreement(measured, reference) == pytest.approx(1.0)

    def test_none_within_two_mm(self) -> None:
        measured = [25.0, 30.0, 18.0]
        reference = [30.0, 35.0, 23.0]
        assert essential_agreement(measured, reference) == pytest.approx(0.0)

    def test_half_within_two_mm(self) -> None:
        measured = [25.0, 25.0]
        reference = [26.0, 30.0]
        assert essential_agreement(measured, reference) == pytest.approx(0.5)

    def test_exact_boundary_counts_as_within(self) -> None:
        measured = [25.0, 23.0]
        reference = [27.0, 25.0]
        assert essential_agreement(measured, reference) == pytest.approx(1.0)

    def test_rank_then_ea_pipeline(self) -> None:
        """Rank-match followed by EA gives correct result on unsorted input."""
        measured = [30.0, 10.0, 20.0]
        reference = [31.0, 11.0, 18.0]
        pairs = match_diameters_by_rank(measured, reference)
        m_vals = [p[0] for p in pairs]
        r_vals = [p[1] for p in pairs]
        # 10->11 (1mm), 20->18 (2mm), 30->31 (1mm): all within 2mm -> EA=100%
        assert essential_agreement(m_vals, r_vals) == pytest.approx(1.0)
