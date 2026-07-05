"""FastAPI REST API for the BacterioScope pipeline.

This module exposes the analysis pipeline as an HTTP service so that any
program — a mobile app, a laboratory information system, or another service —
can submit a plate photograph and receive S/I/R classifications as JSON,
without needing to install Python locally.

Endpoints
---------
``GET /health``
    Returns ``{"status": "ok", "version": "0.1.0"}``.  Use this to check
    that the service is running before sending images.
``POST /analyze``
    Accepts a multipart form upload with a JPEG, PNG, BMP, or TIFF image.
    Returns the full analysis result (disk count, zone diameters, S/I/R
    categories) as JSON.

Security
--------
- Content-type is validated against an allowlist before the image is read.
- File size is capped at 50 MB.
- All error responses from unhandled exceptions return a generic 500 message
  to avoid leaking internal stack traces.

Run with:
    uvicorn bacterioscope.api.routes:app --reload
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from bacterioscope.api.schemas import AnalyzeResponse, DiskAnalysisItem, HealthResponse
from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig

_VERSION = "0.1.0"
_MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024  # 50 MB
_ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/bmp", "image/tiff", "image/tif"}
)
_ALLOWED_SUFFIXES: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
)

app = FastAPI(
    title="BacterioScope",
    description="Automated Kirby-Bauer antibiogram analysis.",
    version=_VERSION,
)

_pipeline: BacterioScopePipeline | None = None


def _get_pipeline() -> BacterioScopePipeline:
    """Return the shared pipeline instance, creating it on the first request.

    Lazy initialisation avoids loading the YOLOv8 model at import time so
    the server starts fast.  The singleton is reused for all subsequent
    ``/analyze`` requests.

    Returns:
        The global ``BacterioScopePipeline`` instance.
    """
    global _pipeline
    if _pipeline is None:
        _pipeline = BacterioScopePipeline(PipelineConfig())
    return _pipeline


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Return service status and version."""
    return HealthResponse(status="ok", version=_VERSION)


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
async def analyze(image: UploadFile = File(...)) -> AnalyzeResponse:
    """Analyze an antibiogram plate image.

    Accepts a multipart image upload (JPEG, PNG, BMP, TIFF).
    Returns disk detection results, zone diameters, and CLSI S/I/R categories.

    Raises:
        HTTPException 415: If the file content type is not a supported image format.
        HTTPException 413: If the file exceeds the 50 MB size limit.
        HTTPException 422: If the image cannot be decoded or the pipeline fails.
    """
    content_type = image.content_type or ""
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type '{content_type}'. "
            f"Accepted: {sorted(_ALLOWED_CONTENT_TYPES)}.",
        )

    data = await image.read()
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the 50 MB size limit.")

    suffix = Path(image.filename or "upload.jpg").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        suffix = ".jpg"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        result = _get_pipeline().analyze(tmp_path)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return AnalyzeResponse(
        image_path=result.image_path,
        plate_diameter_px=result.plate_diameter_px,
        px_per_mm=result.px_per_mm,
        disk_count=len(result.classifications),
        results=[
            DiskAnalysisItem(
                antibiotic=cls.antibiotic,
                zone_diameter_mm=round(cls.zone_diameter_mm, 1),
                category=cls.category,
                breakpoints=cls.breakpoints,
            )
            for cls in result.classifications
        ],
    )


@app.exception_handler(Exception)
async def _generic_handler(request: object, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
