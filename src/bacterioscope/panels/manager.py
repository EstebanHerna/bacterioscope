"""Panel configuration manager for fixed antibiotic disk layouts.

A panel is a YAML file that declares the ordered list of antibiotics placed
on the plate by the laboratory.  Positions are numbered starting at 1 from
the 12 o'clock orientation and proceeding clockwise.

The manager sorts detected disks by their angular position from the plate
centre and maps them to the panel in position order.  When the number of
detected disks does not match the panel, assignment is skipped and a None
is returned rather than producing a silently wrong mapping.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

from bacterioscope.detection.detector import DiskResult

_DEFAULT_PANEL_DIR = Path(__file__).parent.parent.parent.parent / "panels"


@dataclass
class PanelConfig:
    """Configuration for a fixed antibiotic disk panel.

    Attributes:
        name: Human-readable panel name.
        organism_group: CLSI/EUCAST organism group this panel targets.
        standard: Reference standard used for breakpoints (CLSI or EUCAST).
        antibiotics: Antibiotic names in clockwise position order starting at
            position 1 (12 o'clock).
    """

    name: str
    organism_group: str
    standard: str
    antibiotics: list[str]


class PanelManager:
    """Load panel configurations and assign antibiotics by angular disk position.

    Args:
        panel_dir: Directory containing panel YAML files. Defaults to the
            repo-level ``panels/`` directory.
    """

    def __init__(self, panel_dir: Path | None = None) -> None:
        self._dir = panel_dir if panel_dir is not None else _DEFAULT_PANEL_DIR

    def list_panels(self) -> list[str]:
        """Return names (without .yaml) of all available panels.

        Returns:
            Sorted list of panel name strings.
        """
        if not self._dir.exists():
            return []
        return sorted(p.stem for p in self._dir.glob("*.yaml"))

    def load(self, name: str) -> PanelConfig:
        """Load a panel configuration from a YAML file.

        Args:
            name: Panel file stem (without .yaml extension).

        Returns:
            PanelConfig with antibiotics ordered by position field.

        Raises:
            FileNotFoundError: When no matching YAML file exists.
        """
        path = self._dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Panel '{name}' not found in {self._dir}")
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        disks = sorted(data["disks"], key=lambda d: int(d["position"]))
        return PanelConfig(
            name=data["name"],
            organism_group=data.get("organism_group", ""),
            standard=data.get("standard", "CLSI"),
            antibiotics=[d["antibiotic"] for d in disks],
        )

    def assign(
        self,
        disks: list[DiskResult],
        panel: PanelConfig,
        plate_center: tuple[int, int],
    ) -> list[str] | None:
        """Map detected disks to panel antibiotics by clockwise angular position.

        Disk at the 12 o'clock position (smallest clockwise angle) receives
        panel.antibiotics[0], advancing clockwise.

        Args:
            disks: Detected disk list in pipeline order.
            panel: Loaded panel configuration.
            plate_center: (x, y) pixel coordinates of the plate centre.

        Returns:
            Antibiotic names in pipeline disk order, or None when detected
            disk count does not match the panel length.
        """
        if len(disks) != len(panel.antibiotics):
            return None
        cx, cy = plate_center

        def _angle(disk: DiskResult) -> float:
            dx = float(disk.center_x - cx)
            dy = float(disk.center_y - cy)
            return math.atan2(dx, -dy) % (2.0 * math.pi)

        sorted_idx = sorted(range(len(disks)), key=lambda i: _angle(disks[i]))
        labels: list[str] = [""] * len(disks)
        for rank, orig_idx in enumerate(sorted_idx):
            labels[orig_idx] = panel.antibiotics[rank]
        return labels
