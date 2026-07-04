"""Pydantic schemas for the BacterioScope REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DiskAnalysisItem(BaseModel):
    """Classification result for a single antibiotic disk."""

    antibiotic: str = Field(description="Antibiotic name as detected or classified.")
    zone_diameter_mm: float = Field(ge=0.0, description="Inhibition zone diameter in mm.")
    category: str = Field(description="S/I/R category per CLSI 2023 breakpoints.")
    breakpoints: dict[str, float] = Field(
        description="CLSI 2023 S/I/R breakpoint thresholds used for classification."
    )


class AnalyzeResponse(BaseModel):
    """Full analysis result for one antibiogram plate image."""

    image_path: str = Field(description="Path or name of the analyzed image.")
    plate_diameter_px: float = Field(ge=0.0, description="Detected plate diameter in pixels.")
    px_per_mm: float = Field(gt=0.0, description="Calibration factor: pixels per millimetre.")
    disk_count: int = Field(ge=0, description="Number of antibiotic disks detected.")
    results: list[DiskAnalysisItem] = Field(
        description="Per-disk classification results."
    )


class HealthResponse(BaseModel):
    """API health check response."""

    status: str = Field(description="Service status. 'ok' when healthy.")
    version: str = Field(description="BacterioScope package version.")
