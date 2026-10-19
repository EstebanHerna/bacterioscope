"""Plate-review sessions shared by the light-box API and the MCP server.

One analysis becomes one session: the pipeline result (stripped of images and
masks, since a zone mask is full-canvas sized), the antibiotic assigned to each
disk, and any manual diameter corrections. Sessions live in a small in-memory
LRU keyed by ``analysis_id``. A correction blocks the agent review: the report
contract cannot yet trace a manual diameter, so the agent never sees one.

Errors are domain exceptions; each front end maps them to its own protocol
(HTTP status codes in ``api/lab.py``, tool errors in ``mcp_server.py``).
"""

from __future__ import annotations

import math
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from bacterioscope.classification.clsi import CLSI_2023_ENTEROBACTERIACEAE
from bacterioscope.evaluation.synthetic_benchmark import load_synthetic_truth, match_detections
from bacterioscope.panels.manager import PanelManager
from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline, PipelineConfig
from bacterioscope.utils.calibration import detect_plate_circle

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_DIR = REPO_ROOT / "examples" / "synthetic"
REAL_DIR = REPO_ROOT / "examples" / "real"
REAL_SAMPLES = ("real_plate_box4.jpg",)
PLATE_DIAMETER_MM = 90.0
MAX_CORRECTION_MM = 90.0
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"})
_CACHE_SIZE = 48
_CONTOUR_EPSILON_PX = 1.2
_TIERS = ("nano", "super", "ultra")


class SessionError(Exception):
    """Base class for plate-session errors with a user-facing message."""


class NotFoundError(SessionError):
    """An unknown sample, panel, or an expired analysis."""


class InvalidRequestError(SessionError):
    """Inputs that cannot be applied to this analysis."""


class ReviewBlockedError(SessionError):
    """The agent review cannot run while manual corrections exist."""


@dataclass
class Session:
    """One analyzed plate and the reviewer's edits to it."""

    result: AnalysisResult
    sample_id: str | None
    labels: list[str | None] = field(default_factory=list)
    overrides: dict[int, float] = field(default_factory=dict)
    order: list[int] = field(default_factory=list)


_sessions: OrderedDict[str, Session] = OrderedDict()
_lock = threading.Lock()
_pipeline: BacterioScopePipeline | None = None
_models: dict[str, str] | None = None


def get_pipeline() -> BacterioScopePipeline:
    """Return the process-wide pipeline, building it on first use."""
    global _pipeline
    if _pipeline is None:
        _pipeline = BacterioScopePipeline(PipelineConfig())
    return _pipeline


def samples() -> dict[str, dict[str, Any]]:
    """Map each bundled sample id to its image path and synthetic flag."""
    registry: dict[str, dict[str, Any]] = {}
    for name in REAL_SAMPLES:
        path = REAL_DIR / name
        if path.is_file():
            registry[path.stem] = {"path": path, "synthetic": False}
    for path in sorted(SYNTHETIC_DIR.glob("plate_*.png")):
        registry[path.stem] = {"path": path, "synthetic": True}
    return registry


def sample_path(sample_id: str) -> Path:
    """Resolve a sample id to its image; only registry ids resolve.

    Raises:
        NotFoundError: The id is not a bundled sample.
    """
    info = samples().get(sample_id)
    if info is None:
        raise NotFoundError(f"Unknown sample '{sample_id}'.")
    path: Path = info["path"]
    return path


def synthetic_disk_counts() -> dict[str, int]:
    """Return the drawn disk count of every synthetic sample."""
    truth_path = SYNTHETIC_DIR / "ground_truth.json"
    if not truth_path.is_file():
        return {}
    return {Path(p.image).stem: len(p.disks) for p in load_synthetic_truth(truth_path)}


def get_session(analysis_id: str) -> Session:
    """Return a stored session.

    Raises:
        NotFoundError: The analysis expired from the LRU or never existed.
    """
    with _lock:
        session = _sessions.get(analysis_id)
    if session is None:
        raise NotFoundError("Analysis expired; analyze the plate again.")
    return session


def _store(session: Session) -> None:
    key = session.result.analysis_id
    with _lock:
        _sessions[key] = session
        _sessions.move_to_end(key)
        while len(_sessions) > _CACHE_SIZE:
            _sessions.popitem(last=False)


def _contour(mask: NDArray[np.uint8] | None, scale: float) -> list[list[float]]:
    if mask is None:
        return []
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    largest = max(contours, key=cv2.contourArea)
    simplified = cv2.approxPolyDP(largest, _CONTOUR_EPSILON_PX, True)
    return [[round(float(x) / scale, 1), round(float(y) / scale, 1)] for x, y in simplified[:, 0]]


def _plate_circle(result: AnalysisResult, scale: float) -> dict[str, float]:
    image = result.original_image
    circle = detect_plate_circle(image) if image is not None else None
    if circle is not None:
        cx, cy, radius = (float(v) for v in circle)
    else:
        cx, cy = (float(v) for v in result.plate_center)
        radius = result.plate_diameter_px / 2
    return {"cx": cx / scale, "cy": cy / scale, "r": radius / scale}


def _suggested_labels(sample_id: str | None, result: AnalysisResult) -> list[str | None]:
    labels: list[str | None] = [None] * len(result.disks)
    truth_path = SYNTHETIC_DIR / "ground_truth.json"
    if sample_id is None or not truth_path.is_file():
        return labels
    plate = {Path(p.image).stem: p for p in load_synthetic_truth(truth_path)}.get(sample_id)
    if plate is None:
        return labels
    scale = result.canonical_scale_factor or 1.0
    centers = [(d.center_x / scale, d.center_y / scale) for d in result.disks]
    for disk_truth, detection in zip(plate.disks, match_detections(plate, centers)):
        if detection is not None:
            labels[detection] = disk_truth.antibiotic
    return labels


def _slim(result: AnalysisResult) -> AnalysisResult:
    return replace(
        result, annotated_image=None, original_image=None,
        zones=[replace(zone, mask=None) for zone in result.zones],
    )


def _disk_payload(result: AnalysisResult, scale: float) -> list[dict[str, Any]]:
    return [
        {
            "index": i,
            "center": [disk.center_x / scale, disk.center_y / scale],
            "disk_radius": disk.radius_px / scale,
            "zone_radius": zone.radius_px / scale,
            "diameter_mm": round(zone.diameter_mm, 2),
            "circularity": round(zone.circularity, 3),
            "flags": list(result.flags[i]) if i < len(result.flags) else [],
            "contour": _contour(zone.mask, scale),
        }
        for i, (disk, zone) in enumerate(zip(result.disks, result.zones))
    ]


def _plate_payload(
    result: AnalysisResult, sample_id: str | None, size: tuple[int, int]
) -> dict[str, Any]:
    scale = result.canonical_scale_factor or 1.0
    return {
        "analysis_id": result.analysis_id,
        "sample_id": sample_id,
        "image": {"width": size[0], "height": size[1]},
        "calibration": {
            "px_per_mm": result.px_per_mm / scale,
            "plate": _plate_circle(result, scale),
            "plate_diameter_mm": PLATE_DIAMETER_MM,
        },
        "disks": _disk_payload(result, scale),
        "suggested_labels": _suggested_labels(sample_id, result),
        "antibiotics": sorted(CLSI_2023_ENTEROBACTERIACEAE),
        "panels": PanelManager().list_panels(),
        "traceability": {
            "analysis_id": result.analysis_id,
            "image_sha256": result.image_sha256,
            "commit_hash": result.commit_hash,
            "software_version": result.software_version,
            "breakpoint_table_version": result.breakpoint_table_version,
        },
        "timings_ms": {k: round(v, 1) for k, v in result.timings_ms.items()},
    }


def analyze_path(path: Path, sample_id: str | None = None) -> dict[str, Any]:
    """Run the pipeline on one image, store the session, return its geometry.

    Args:
        path: Image file to analyze.
        sample_id: Bundled sample id, used to suggest the known disk layout.

    Returns:
        Plate payload: calibration, plate circle, per-disk geometry and
        diameters, suggested labels, available antibiotics and panels, and
        traceability fields. Coordinates are in original-image pixels.

    Raises:
        InvalidRequestError: The pipeline could not read or analyze the image.
    """
    try:
        result = get_pipeline().analyze(path)
    except (ValueError, FileNotFoundError) as exc:
        raise InvalidRequestError(str(exc)) from exc
    image = cv2.imread(str(path))
    size = (int(image.shape[1]), int(image.shape[0])) if image is not None else (0, 0)
    payload = _plate_payload(result, sample_id, size)
    _store(Session(
        _slim(result), sample_id,
        labels=list(payload["suggested_labels"]), order=clockwise_order(payload),
    ))
    return payload


def clockwise_order(payload: dict[str, Any]) -> list[int]:
    """Disk indices sorted clockwise from 12 o'clock around the plate centre."""
    plate = payload["calibration"]["plate"]

    def angle(disk: dict[str, Any]) -> float:
        dx = disk["center"][0] - plate["cx"]
        dy = disk["center"][1] - plate["cy"]
        return math.atan2(dx, -dy) % (2 * math.pi)

    return [d["index"] for d in sorted(payload["disks"], key=angle)]


def _validate(
    result: AnalysisResult, labels: list[str | None], overrides: dict[int, float]
) -> None:
    if len(labels) != len(result.disks):
        raise InvalidRequestError(
            f"One label per detected disk is required ({len(result.disks)} disks)."
        )
    bad = [
        i for i, mm in overrides.items()
        if not 0 <= i < len(result.disks) or not 0 < mm <= MAX_CORRECTION_MM
    ]
    if bad:
        raise InvalidRequestError(f"Invalid corrections for disks {bad}.")


def classify(
    analysis_id: str, labels: list[str | None], overrides: dict[int, float]
) -> dict[str, Any]:
    """Store the assignment and corrections, then recompute every category.

    Args:
        analysis_id: Session to update.
        labels: Antibiotic per disk index; ``None`` leaves a disk unassigned.
        overrides: Corrected diameter in mm per disk index.

    Returns:
        ``{"analysis_id", "disks": [...], "corrections"}`` with, per disk, the
        antibiotic, measured and effective diameter, category and breakpoints.

    Raises:
        NotFoundError: The analysis expired.
        InvalidRequestError: Wrong label count or out-of-range corrections.
    """
    session = get_session(analysis_id)
    result = session.result
    _validate(result, labels, overrides)
    session.labels, session.overrides = list(labels), dict(overrides)
    classifier = get_pipeline().classifier
    rows = []
    for i, zone in enumerate(result.zones):
        mm = overrides.get(i, zone.diameter_mm)
        label = labels[i]
        cls = classifier.classify(label, mm) if label else None
        rows.append({
            "index": i, "antibiotic": label, "measured_mm": round(zone.diameter_mm, 2),
            "diameter_mm": round(mm, 2), "corrected": i in overrides,
            "category": cls.category if cls else "UNKNOWN",
            "breakpoints": cls.breakpoints if cls else {},
            "flags": list(result.flags[i]) if i < len(result.flags) else [],
        })
    return {"analysis_id": analysis_id, "disks": rows, "corrections": len(overrides)}


def panel_labels(analysis_id: str, name: str) -> list[str | None]:
    """Assign antibiotics clockwise from 12 o'clock using a fixed panel layout.

    Raises:
        NotFoundError: The analysis expired or the panel does not exist.
        InvalidRequestError: The panel size differs from the detected disk count.
    """
    session = get_session(analysis_id)
    manager = PanelManager()
    if name not in manager.list_panels():
        raise NotFoundError(f"Unknown panel '{name}'.")
    panel = manager.load(name)
    labels = manager.assign(session.result.disks, panel, session.result.plate_center)
    if labels is None:
        raise InvalidRequestError(
            f"The panel has {len(panel.antibiotics)} positions; "
            f"{len(session.result.disks)} disks were detected."
        )
    return list(labels)


def review_client() -> Any:
    """TokenFactoryClient with live-resolved tier models, or an unconfigured one."""
    global _models
    from bacterioscope.agent.nemotron_client import (
        TokenFactoryClient,
        TokenFactoryConfigurationError,
        TokenFactoryRequestError,
    )
    from bacterioscope.evaluation.agent_benchmark import resolve_tier_models

    if _models is None and os.getenv("NEBIUS_API_KEY", "").strip():
        overrides = {tier: os.getenv(f"NEBIUS_MODEL_{tier.upper()}", "") for tier in _TIERS}
        try:
            catalog = TokenFactoryClient(models={}).list_models()
            _models = resolve_tier_models(catalog, overrides)
        except (TokenFactoryConfigurationError, TokenFactoryRequestError, ValueError):
            _models = {}
    return TokenFactoryClient(models=_models or {})


def review(analysis_id: str, organism: str, alerts: bool) -> dict[str, Any]:
    """Run the grounded agent review on a session's current assignment.

    Args:
        analysis_id: Session to review.
        organism: Identified organism, e.g. ``"Escherichia coli"``.
        alerts: Whether to search INS and OPS public alerts.

    Returns:
        ``{"status", "fallback_reason", "report"}``; without a Nebius key the
        status is ``"fallback"`` and the deterministic report is complete.

    Raises:
        NotFoundError: The analysis expired.
        ReviewBlockedError: The session carries manual corrections.
    """
    session = get_session(analysis_id)
    if session.overrides:
        raise ReviewBlockedError(
            "Manual corrections are not traceable in the report yet; clear them to review."
        )
    from bacterioscope.agent.orchestrator import review_plate

    labels = [label or f"disk_{i}" for i, label in enumerate(session.labels)]
    labeled = get_pipeline().reclassify_with_labels(session.result, labels)
    outcome = review_plate(
        labeled, organism=organism, client=review_client(),
        alert_sources=("ins", "ops") if alerts else (),
    )
    return {"status": outcome.status, "fallback_reason": outcome.fallback_reason,
            "report": outcome.report}
