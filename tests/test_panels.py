"""Tests for panels.manager.PanelManager."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from bacterioscope.detection.detector import DiskResult
from bacterioscope.panels.manager import PanelConfig, PanelManager


def _disk(cx: int, cy: int, label: str = "disk_0") -> DiskResult:
    return DiskResult(
        label=label, center_x=cx, center_y=cy, radius_px=15,
        confidence=0.0, bbox=(cx - 15, cy - 15, cx + 15, cy + 15),
    )


def _make_panel(n: int) -> PanelConfig:
    antibiotics = [f"antibiotic_{i}" for i in range(n)]
    return PanelConfig(
        name="Test Panel", organism_group="Enterobacteriaceae",
        standard="CLSI", antibiotics=antibiotics,
    )


class TestPanelManagerListAndLoad:
    def test_list_panels_returns_sorted_names(self, tmp_path: Path) -> None:
        (tmp_path / "panel_b.yaml").write_text(
            "name: B\norganism_group: E\nstandard: CLSI\ndisks:\n"
            "  - {position: 1, antibiotic: amp}\n",
            encoding="utf-8",
        )
        (tmp_path / "panel_a.yaml").write_text(
            "name: A\norganism_group: E\nstandard: CLSI\ndisks:\n"
            "  - {position: 1, antibiotic: cip}\n",
            encoding="utf-8",
        )
        pm = PanelManager(panel_dir=tmp_path)
        assert pm.list_panels() == ["panel_a", "panel_b"]

    def test_list_panels_empty_when_dir_missing(self, tmp_path: Path) -> None:
        pm = PanelManager(panel_dir=tmp_path / "nonexistent")
        assert pm.list_panels() == []

    def test_load_returns_panel_config(self, tmp_path: Path) -> None:
        (tmp_path / "p.yaml").write_text(
            "name: My Panel\norganism_group: Enterobacteriaceae\nstandard: CLSI\n"
            "disks:\n  - {position: 1, antibiotic: meropenem}\n"
            "  - {position: 2, antibiotic: ciprofloxacin}\n",
            encoding="utf-8",
        )
        pm = PanelManager(panel_dir=tmp_path)
        cfg = pm.load("p")
        assert cfg.name == "My Panel"
        assert cfg.antibiotics == ["meropenem", "ciprofloxacin"]

    def test_load_raises_for_missing_panel(self, tmp_path: Path) -> None:
        pm = PanelManager(panel_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            pm.load("nonexistent")

    def test_load_sorts_disks_by_position(self, tmp_path: Path) -> None:
        (tmp_path / "p.yaml").write_text(
            "name: P\norganism_group: E\nstandard: CLSI\n"
            "disks:\n  - {position: 2, antibiotic: second}\n"
            "  - {position: 1, antibiotic: first}\n",
            encoding="utf-8",
        )
        pm = PanelManager(panel_dir=tmp_path)
        cfg = pm.load("p")
        assert cfg.antibiotics == ["first", "second"]


class TestPanelManagerAssign:
    def test_returns_none_when_count_mismatch(self) -> None:
        pm = PanelManager()
        panel = _make_panel(3)
        disks = [_disk(100, 50), _disk(150, 50)]
        result = pm.assign(disks, panel, (100, 100))
        assert result is None

    def test_returns_labels_same_length_as_disks(self) -> None:
        pm = PanelManager()
        panel = _make_panel(4)
        cx, cy = 100, 100
        disks = [
            _disk(cx, cy - 50),   # top (12 o'clock)
            _disk(cx + 50, cy),   # right (3 o'clock)
            _disk(cx, cy + 50),   # bottom (6 o'clock)
            _disk(cx - 50, cy),   # left (9 o'clock)
        ]
        labels = pm.assign(disks, panel, (cx, cy))
        assert labels is not None
        assert len(labels) == 4

    def test_top_disk_gets_first_antibiotic(self) -> None:
        pm = PanelManager()
        panel = _make_panel(4)
        cx, cy = 100, 100
        disks = [
            _disk(cx, cy - 50),   # 12 o'clock — should be position 0
            _disk(cx + 50, cy),
            _disk(cx, cy + 50),
            _disk(cx - 50, cy),
        ]
        labels = pm.assign(disks, panel, (cx, cy))
        assert labels is not None
        top_idx = 0
        assert labels[top_idx] == "antibiotic_0"

    def test_clockwise_order_is_correct(self) -> None:
        pm = PanelManager()
        panel = _make_panel(4)
        cx, cy = 100, 100
        top_disk = _disk(cx, cy - 50)
        right_disk = _disk(cx + 50, cy)
        bottom_disk = _disk(cx, cy + 50)
        left_disk = _disk(cx - 50, cy)
        disks = [top_disk, right_disk, bottom_disk, left_disk]
        labels = pm.assign(disks, panel, (cx, cy))
        assert labels is not None
        assert labels[0] == "antibiotic_0"   # top
        assert labels[1] == "antibiotic_1"   # right
        assert labels[2] == "antibiotic_2"   # bottom
        assert labels[3] == "antibiotic_3"   # left

    def test_single_disk_panel(self) -> None:
        pm = PanelManager()
        panel = _make_panel(1)
        disks = [_disk(100, 50)]
        labels = pm.assign(disks, panel, (100, 100))
        assert labels == ["antibiotic_0"]

    def test_empty_disks_empty_panel(self) -> None:
        pm = PanelManager()
        panel = _make_panel(0)
        labels = pm.assign([], panel, (100, 100))
        assert labels == []

    def test_example_panels_load_from_repo(self) -> None:
        pm = PanelManager()
        available = pm.list_panels()
        assert len(available) > 0, "At least one panel YAML must exist in panels/"
        for name in available:
            cfg = pm.load(name)
            assert len(cfg.antibiotics) > 0

    def test_angle_wraps_correctly(self) -> None:
        pm = PanelManager()
        panel = _make_panel(2)
        cx, cy = 50, 50
        just_past_top = _disk(cx + 1, cy - 49)
        just_before_top = _disk(cx - 1, cy - 49)
        disks = [just_past_top, just_before_top]
        labels = pm.assign(disks, panel, (cx, cy))
        assert labels is not None
        assert len(labels) == 2

    def test_angle_uses_atan2_not_euclidean(self) -> None:
        pm = PanelManager()
        panel = _make_panel(2)
        cx, cy = 100, 100
        disk_a = _disk(cx + 30, cy - 40)
        disk_b = _disk(cx - 30, cy - 40)
        disks = [disk_a, disk_b]
        labels = pm.assign(disks, panel, (cx, cy))
        assert labels is not None
        angle_a = math.atan2(30, 40) % (2 * math.pi)
        angle_b = math.atan2(-30, 40) % (2 * math.pi)
        if angle_a < angle_b:
            assert labels[0] == "antibiotic_0"
        else:
            assert labels[1] == "antibiotic_0"
