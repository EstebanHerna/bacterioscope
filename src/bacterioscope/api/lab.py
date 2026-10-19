"""Lab-review endpoints behind the light-box web app (``src/bacterioscope/web``).

``POST /analyze`` stays the stable, compact contract for other programs. These
routes serve the interactive review instead: the plate geometry needed to
draw every measurement on the photo (centres, contours, the plate rim), live
reclassification when a microbiologist assigns antibiotics or corrects a
zone, and the Nemotron review through ``agent.orchestrator.review_plate``.

Analyses are kept in a small in-memory LRU, stripped of images and masks
(a zone mask is full-canvas sized; sixteen of them per plate add up fast).
A correction is recorded server-side and blocks the agent review: the report
contract cannot yet trace a manual diameter, so the agent never sees one.
"""

from __future__ import annotations

import os
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from bacterioscope.classification.clsi import CLSI_2023_ENTEROBACTERIACEAE
from bacterioscope.evaluation.synthetic_benchmark import load_synthetic_truth, match_detections
from bacterioscope.panels.manager import PanelManager
from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline, PipelineConfig
from bacterioscope.utils.calibration import detect_plate_circle

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SYNTHETIC_DIR = _REPO_ROOT / "examples" / "synthetic"
_REAL_DIR = _REPO_ROOT / "examples" / "real"
_REAL_SAMPLES = ("real_plate_box4.jpg",)
_PLATE_DIAMETER_MM = 90.0
_CACHE_SIZE = 48
_CONTOUR_EPSILON_PX = 1.2
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/bmp", "image/tiff", "image/tif"})
_ALLOWED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"})
_TIERS = ("nano", "super", "ultra")

router = APIRouter(prefix="/api", tags=["lab review"])


@dataclass
class _Entry:
    result: AnalysisResult
    sample_id: str | None
    labels: list[str | None] = field(default_factory=list)
    overrides: dict[int, float] = field(default_factory=dict)


_cache: OrderedDict[str, _Entry] = OrderedDict()
_cache_lock = threading.Lock()
_pipeline: BacterioScopePipeline | None = None
_models: dict[str, str] | None = None


def _get_pipeline() -> BacterioScopePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = BacterioScopePipeline(PipelineConfig())
    return _pipeline


def _samples() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for name in _REAL_SAMPLES:
        path = _REAL_DIR / name
        if path.is_file():
            registry[path.stem] = {"path": path, "synthetic": False}
    for path in sorted(_SYNTHETIC_DIR.glob("plate_*.png")):
        registry[path.stem] = {"path": path, "synthetic": True}
    return registry


class SampleItem(BaseModel):
    """One plate the app can load without an upload."""

    id: str
    synthetic: bool
    image_url: str
    disks: int | None = Field(description="Drawn disk count for synthetic plates.")


@router.get("/samples", response_model=list[SampleItem])
def list_samples() -> list[SampleItem]:
    """List the bundled sample plates (synthetic ones carry a known layout)."""
    counts = {}
    truth_path = _SYNTHETIC_DIR / "ground_truth.json"
    if truth_path.is_file():
        counts = {Path(p.image).stem: len(p.disks) for p in load_synthetic_truth(truth_path)}
    return [
        SampleItem(
            id=sample_id, synthetic=info["synthetic"],
            image_url=f"/api/samples/{sample_id}/image", disks=counts.get(sample_id),
        )
        for sample_id, info in _samples().items()
    ]


@router.get("/samples/{sample_id}/image")
def sample_image(sample_id: str) -> FileResponse:
    """Serve one bundled sample image; only registry ids resolve to a file."""
    info = _samples().get(sample_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Unknown sample.")
    return FileResponse(info["path"])


def _store(entry: _Entry) -> str:
    key = entry.result.analysis_id
    with _cache_lock:
        _cache[key] = entry
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
    return key


def _entry(analysis_id: str) -> _Entry:
    with _cache_lock:
        entry = _cache.get(analysis_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Analysis expired; analyze the plate again.")
    return entry


def _contour(mask: np.ndarray | None, scale: float) -> list[list[float]]:
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
    truth_path = _SYNTHETIC_DIR / "ground_truth.json"
    if sample_id is None or not truth_path.is_file():
        return labels
    plates = {Path(p.image).stem: p for p in load_synthetic_truth(truth_path)}
    plate = plates.get(sample_id)
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
            "plate_diameter_mm": _PLATE_DIAMETER_MM,
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


def _analyze_path(path: Path, sample_id: str | None) -> dict[str, Any]:
    try:
        result = _get_pipeline().analyze(path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    image = cv2.imread(str(path))
    size = (int(image.shape[1]), int(image.shape[0])) if image is not None else (0, 0)
    payload = _plate_payload(result, sample_id, size)
    _store(_Entry(_slim(result), sample_id, labels=list(payload["suggested_labels"])))
    return payload


@router.post("/plates")
async def analyze_plate(
    image: UploadFile | None = File(default=None),
    sample_id: str | None = Form(default=None),
) -> dict[str, Any]:
    """Analyze an uploaded photo or a bundled sample and return its geometry."""
    if sample_id is not None:
        info = _samples().get(sample_id)
        if info is None:
            raise HTTPException(status_code=404, detail="Unknown sample.")
        return _analyze_path(info["path"], sample_id)
    if image is None:
        raise HTTPException(status_code=422, detail="Send an image or a sample_id.")
    if (image.content_type or "") not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Send a JPEG, PNG, BMP or TIFF photo.")
    data = await image.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The photo exceeds 50 MB.")
    suffix = Path(image.filename or "plate.jpg").suffix.lower()
    with tempfile.NamedTemporaryFile(
        suffix=suffix if suffix in _ALLOWED_SUFFIXES else ".jpg", delete=False
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return _analyze_path(tmp_path, None)
    finally:
        tmp_path.unlink(missing_ok=True)


class ClassifyRequest(BaseModel):
    """Antibiotic per disk (null = unassigned) and corrected diameters."""

    labels: list[str | None]
    overrides: dict[int, float] = Field(default_factory=dict)


@router.post("/plates/{analysis_id}/classify")
def classify_plate(analysis_id: str, body: ClassifyRequest) -> dict[str, Any]:
    """Recompute every category from the assigned antibiotics and corrections."""
    entry = _entry(analysis_id)
    result = entry.result
    if len(body.labels) != len(result.disks):
        raise HTTPException(status_code=422, detail="One label per detected disk is required.")
    bad = [
        i for i, mm in body.overrides.items()
        if not 0 <= i < len(result.disks) or not 0 < mm <= 90
    ]
    if bad:
        raise HTTPException(status_code=422, detail=f"Invalid corrections for disks {bad}.")
    entry.labels, entry.overrides = list(body.labels), dict(body.overrides)
    classifier = _get_pipeline().classifier
    rows = []
    for i, zone in enumerate(result.zones):
        mm = body.overrides.get(i, zone.diameter_mm)
        label = body.labels[i]
        cls = classifier.classify(label, mm) if label else None
        rows.append({
            "index": i, "antibiotic": label, "measured_mm": round(zone.diameter_mm, 2),
            "diameter_mm": round(mm, 2), "corrected": i in body.overrides,
            "category": cls.category if cls else "UNKNOWN",
            "breakpoints": cls.breakpoints if cls else {},
        })
    return {"analysis_id": analysis_id, "disks": rows, "corrections": len(body.overrides)}


def _review_client() -> Any:
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


class ReviewRequest(BaseModel):
    """Inputs for the Nemotron review of one analyzed plate."""

    organism: str = Field(min_length=1, max_length=120)
    alerts: bool = True


@router.post("/plates/{analysis_id}/review")
def review(analysis_id: str, body: ReviewRequest) -> dict[str, Any]:
    """Run the grounded agent review; manual corrections block it."""
    entry = _entry(analysis_id)
    if entry.overrides:
        raise HTTPException(
            status_code=409,
            detail="Manual corrections are not traceable in the report yet; clear them to review.",
        )
    from bacterioscope.agent.orchestrator import review_plate

    labels = [label or f"disk_{i}" for i, label in enumerate(entry.labels)]
    labeled = _get_pipeline().reclassify_with_labels(entry.result, labels)
    outcome = review_plate(
        labeled, organism=body.organism, client=_review_client(),
        alert_sources=("ins", "ops") if body.alerts else (),
    )
    return {"status": outcome.status, "fallback_reason": outcome.fallback_reason,
            "report": outcome.report}


class PanelRequest(BaseModel):
    """Name of a panel YAML in ``panels/``."""

    name: str = Field(min_length=1, max_length=80)


@router.post("/plates/{analysis_id}/panel")
def apply_panel(analysis_id: str, body: PanelRequest) -> dict[str, Any]:
    """Assign antibiotics clockwise from 12 o'clock using a fixed panel layout."""
    entry = _entry(analysis_id)
    manager = PanelManager()
    if body.name not in manager.list_panels():
        raise HTTPException(status_code=404, detail="Unknown panel.")
    panel = manager.load(body.name)
    labels = manager.assign(entry.result.disks, panel, entry.result.plate_center)
    if labels is None:
        raise HTTPException(
            status_code=422,
            detail=f"The panel has {len(panel.antibiotics)} positions; "
            f"{len(entry.result.disks)} disks were detected.",
        )
    return {"analysis_id": analysis_id, "labels": labels}
