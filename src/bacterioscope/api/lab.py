"""Lab-review endpoints behind the light-box web app (``src/bacterioscope/web``).

``POST /analyze`` stays the stable, compact contract for other programs. These
routes serve the interactive review instead: the plate geometry needed to
draw every measurement on the photo (centres, contours, the plate rim), live
reclassification when a microbiologist assigns antibiotics or corrects a
zone, and the Nemotron review. The session logic lives in
``bacterioscope.plate_session``, shared with the MCP server; this module only
maps it to HTTP.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from bacterioscope import plate_session
from bacterioscope.plate_session import (
    InvalidRequestError,
    NotFoundError,
    ReviewBlockedError,
    SessionError,
)

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_ALLOWED_TYPES = frozenset({"image/jpeg", "image/png", "image/bmp", "image/tiff", "image/tif"})
_STATUS = {NotFoundError: 404, InvalidRequestError: 422, ReviewBlockedError: 409}

router = APIRouter(prefix="/api", tags=["lab review"])


def _http(exc: SessionError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(type(exc), 400), detail=str(exc))


class SampleItem(BaseModel):
    """One plate the app can load without an upload."""

    id: str
    synthetic: bool
    image_url: str
    disks: int | None = Field(description="Drawn disk count for synthetic plates.")


@router.get("/samples", response_model=list[SampleItem])
def list_samples() -> list[SampleItem]:
    """List the bundled sample plates (synthetic ones carry a known layout)."""
    counts = plate_session.synthetic_disk_counts()
    return [
        SampleItem(
            id=sample_id, synthetic=info["synthetic"],
            image_url=f"/api/samples/{sample_id}/image", disks=counts.get(sample_id),
        )
        for sample_id, info in plate_session.samples().items()
    ]


@router.get("/samples/{sample_id}/image")
def sample_image(sample_id: str) -> FileResponse:
    """Serve one bundled sample image; only registry ids resolve to a file."""
    try:
        return FileResponse(plate_session.sample_path(sample_id))
    except SessionError as exc:
        raise _http(exc) from exc


async def _analyze_upload(image: UploadFile) -> dict[str, Any]:
    if (image.content_type or "") not in _ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail="Send a JPEG, PNG, BMP or TIFF photo.")
    data = await image.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="The photo exceeds 50 MB.")
    suffix = Path(image.filename or "plate.jpg").suffix.lower()
    with tempfile.NamedTemporaryFile(
        suffix=suffix if suffix in plate_session.IMAGE_SUFFIXES else ".jpg", delete=False
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return plate_session.analyze_path(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/plates")
async def analyze_plate(
    image: UploadFile | None = File(default=None),
    sample_id: str | None = Form(default=None),
) -> dict[str, Any]:
    """Analyze an uploaded photo or a bundled sample and return its geometry."""
    try:
        if sample_id is not None:
            return plate_session.analyze_path(plate_session.sample_path(sample_id), sample_id)
        if image is None:
            raise HTTPException(status_code=422, detail="Send an image or a sample_id.")
        return await _analyze_upload(image)
    except SessionError as exc:
        raise _http(exc) from exc


class ClassifyRequest(BaseModel):
    """Antibiotic per disk (null = unassigned) and corrected diameters."""

    labels: list[str | None]
    overrides: dict[int, float] = Field(default_factory=dict)


@router.post("/plates/{analysis_id}/classify")
def classify_plate(analysis_id: str, body: ClassifyRequest) -> dict[str, Any]:
    """Recompute every category from the assigned antibiotics and corrections."""
    try:
        return plate_session.classify(analysis_id, body.labels, body.overrides)
    except SessionError as exc:
        raise _http(exc) from exc


class ReviewRequest(BaseModel):
    """Inputs for the Nemotron review of one analyzed plate."""

    organism: str = Field(min_length=1, max_length=120)
    alerts: bool = True


@router.post("/plates/{analysis_id}/review")
def review(analysis_id: str, body: ReviewRequest) -> dict[str, Any]:
    """Run the grounded agent review; manual corrections block it."""
    try:
        return plate_session.review(analysis_id, body.organism, body.alerts)
    except SessionError as exc:
        raise _http(exc) from exc


class PanelRequest(BaseModel):
    """Name of a panel YAML in ``panels/``."""

    name: str = Field(min_length=1, max_length=80)


@router.post("/plates/{analysis_id}/panel")
def apply_panel(analysis_id: str, body: PanelRequest) -> dict[str, Any]:
    """Assign antibiotics clockwise from 12 o'clock using a fixed panel layout."""
    try:
        labels = plate_session.panel_labels(analysis_id, body.name)
    except SessionError as exc:
        raise _http(exc) from exc
    return {"analysis_id": analysis_id, "labels": labels}
