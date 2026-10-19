"""MCP server exposing BacterioScope plate reading to LLM clients.

Tools cover the same workflow as the light-box web app, through the shared
``plate_session`` module: analyze a Kirby-Bauer plate photo, assign the
antibiotic on each disk and correct diameters, look up CLSI M100-Ed33
breakpoints, and run the grounded Nemotron review. Disks are addressed by
clockwise position from 12 o'clock (position 1), the convention panels use.

Run over stdio (default) with ``bacterioscope-mcp``, or over streamable HTTP
bound to localhost with ``bacterioscope-mcp --transport streamable-http``.
Every output is decision support for a microbiologist, not a clinical result.
"""

from __future__ import annotations

import argparse
import json
import math
from enum import Enum
from pathlib import Path
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

from bacterioscope import plate_session
from bacterioscope.classification.clsi import CLSI_2023_ENTEROBACTERIACEAE, CLSIClassifier
from bacterioscope.panels.manager import PanelManager
from bacterioscope.plate_session import SessionError

MAX_IMAGE_BYTES = 50 * 1024 * 1024
NEAR_BREAKPOINT_MM = 2.0
CLSI_EDITION = "CLSI M100-Ed33 (2023), Enterobacterales"
DISCLAIMER = (
    "Decision support only, not a medical device: a microbiologist must review and sign "
    "every result. Accuracy on real clinical photos is still far below the clinical target."
)
ABBREVIATIONS = {
    "MEM": "meropenem", "IPM": "imipenem", "ETP": "ertapenem", "DOR": "doripenem",
    "AMP": "ampicillin", "APX": "ampicillin", "AMC": "amoxicillin-clavulanate",
    "AUG": "amoxicillin-clavulanate", "TZP": "piperacillin-tazobactam",
    "PTZ": "piperacillin-tazobactam", "CRO": "ceftriaxone", "CAZ": "ceftazidime",
    "FEP": "cefepime", "CPM": "cefepime", "CIP": "ciprofloxacin", "LVX": "levofloxacin",
    "LEV": "levofloxacin", "LE": "levofloxacin", "GEN": "gentamicin", "GM": "gentamicin",
    "AMK": "amikacin", "AK": "amikacin", "SXT": "trimethoprim-sulfamethoxazole",
}
CODES = {name: code for code, name in reversed(list(ABBREVIATIONS.items()))}

mcp = FastMCP(
    "bacterioscope_mcp",
    instructions=(
        "Read Kirby-Bauer antibiogram plates. Typical flow: bacterioscope_list_samples or a "
        "local image -> bacterioscope_analyze_plate (with antibiotics in clockwise order or a "
        "panel) -> bacterioscope_update_plate to fix assignments or diameters -> "
        "bacterioscope_review_plate. Disks are numbered clockwise from 12 o'clock. "
        "Results are decision support for a microbiologist, never a final clinical report."
    ),
)


class ResponseFormat(str, Enum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


_FORMAT_FIELD = Field(
    default=ResponseFormat.MARKDOWN,
    description="'markdown' for a readable table, 'json' for the complete structured data.",
)


def _resolve_antibiotic(name: str) -> str:
    """Map a name or CLSI abbreviation to a breakpoint-table key."""
    key = name.strip().lower().replace(" ", "-")
    if key in CLSI_2023_ENTEROBACTERIACEAE:
        return key
    code = name.strip().upper().split(" ")[0]
    if code in ABBREVIATIONS:
        return ABBREVIATIONS[code]
    raise ToolError(
        f"Unknown antibiotic '{name}'. Use a name or code from bacterioscope_get_breakpoints, "
        f"e.g. 'ciprofloxacin' or 'CIP'."
    )


def _near_breakpoint(diameter_mm: float, breakpoints: dict[str, float]) -> bool:
    if "S" not in breakpoints:
        return False
    edges = [breakpoints["S"] - 0.5, breakpoints.get("R", -math.inf) + 0.5]
    return any(abs(diameter_mm - edge) < NEAR_BREAKPOINT_MM for edge in edges)


def _session_call(fn: Any, *args: Any) -> Any:
    try:
        return fn(*args)
    except SessionError as exc:
        raise ToolError(str(exc)) from exc


def _plate_rows(analysis_id: str) -> list[dict[str, Any]]:
    """Reclassify a session from its stored state and order rows by position."""
    session = _session_call(plate_session.get_session, analysis_id)
    table = _session_call(plate_session.classify, analysis_id, session.labels, session.overrides)
    rows = []
    for position, index in enumerate(session.order, start=1):
        row = dict(table["disks"][index])
        row["position"] = position
        row["code"] = CODES.get(row["antibiotic"] or "", None)
        row["near_breakpoint"] = _near_breakpoint(row["diameter_mm"], row["breakpoints"])
        rows.append(row)
    return rows


def _plate_markdown(analysis_id: str, rows: list[dict[str, Any]], header: list[str]) -> str:
    lines = [f"# Plate `{analysis_id}`", *header, ""]
    lines.append("| Pos | Antibiotic | Zone (mm) | Category | Notes |")
    lines.append("|---|---|---|---|---|")
    for row in rows:
        drug = f"{row['code']} {row['antibiotic']}" if row["antibiotic"] else "unassigned"
        notes = list(row["flags"])
        if row["corrected"]:
            notes.append(f"corrected (measured {row['measured_mm']})")
        if row["near_breakpoint"]:
            notes.append("within 2 mm of a breakpoint")
        lines.append(
            f"| {row['position']} | {drug} | {row['diameter_mm']:.1f} | {row['category']} "
            f"| {', '.join(notes) or '-'} |"
        )
    lines += ["", f"Breakpoints: {CLSI_EDITION}. Flagged disks are excluded from expert rules.",
              DISCLAIMER]
    return "\n".join(lines)


def _plate_response(analysis_id: str, fmt: ResponseFormat, extra: dict[str, Any]) -> str:
    rows = _plate_rows(analysis_id)
    if fmt == ResponseFormat.JSON:
        body = {"analysis_id": analysis_id, **extra, "standard": CLSI_EDITION,
                "disks": rows, "disclaimer": DISCLAIMER}
        return json.dumps(body, indent=2)
    header = [f"- {key.replace('_', ' ')}: {value}" for key, value in extra.items()
              if not isinstance(value, dict)]
    return _plate_markdown(analysis_id, rows, header)


def _image_file(raw: str) -> Path:
    path = Path(raw).expanduser().resolve()
    if path.suffix.lower() not in plate_session.IMAGE_SUFFIXES:
        raise ToolError("The image must be a JPEG, PNG, BMP or TIFF file.")
    if not path.is_file():
        raise ToolError(f"No file at '{path}'. Pass an absolute path to a plate photo.")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ToolError("The image exceeds 50 MB.")
    return path


def _labels_by_position(order: list[int], antibiotics: list[str | None]) -> list[str | None]:
    if len(antibiotics) != len(order):
        raise ToolError(
            f"{len(order)} disks were detected but {len(antibiotics)} antibiotics were given. "
            "Analyze without antibiotics first, then assign by position with "
            "bacterioscope_update_plate."
        )
    labels: list[str | None] = [None] * len(order)
    for index, name in zip(order, antibiotics):
        labels[index] = _resolve_antibiotic(name) if name else None
    return labels


class AnalyzePlateInput(BaseModel):
    """Inputs for analyzing one plate photo."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    sample_id: str | None = Field(
        default=None, pattern=r"^[a-z0-9_]+$", max_length=80,
        description="Bundled sample id from bacterioscope_list_samples, e.g. 'plate_mixed_sir'.",
    )
    image_path: str | None = Field(
        default=None, min_length=1, max_length=1024,
        description="Absolute path to a local plate photo (JPEG/PNG/BMP/TIFF, top view, "
        "plate rim visible).",
    )
    antibiotics: list[str | None] | None = Field(
        default=None, max_length=32,
        description="Antibiotic per disk in clockwise order from 12 o'clock (names or codes, "
        "null = unassigned). Must match the detected disk count.",
    )
    panel: str | None = Field(
        default=None, max_length=80,
        description="Fixed panel from bacterioscope_list_panels; assigns antibiotics by position.",
    )
    response_format: ResponseFormat = _FORMAT_FIELD

    @model_validator(mode="after")
    def _one_source(self) -> AnalyzePlateInput:
        if (self.sample_id is None) == (self.image_path is None):
            raise ValueError("Give exactly one of sample_id or image_path.")
        if self.antibiotics is not None and self.panel is not None:
            raise ValueError("Give antibiotics or panel, not both.")
        return self


@mcp.tool(
    name="bacterioscope_analyze_plate",
    annotations=ToolAnnotations(
        title="Analyze antibiogram plate", readOnlyHint=False, destructiveHint=False,
        idempotentHint=False, openWorldHint=False,
    ),
)
async def bacterioscope_analyze_plate(params: AnalyzePlateInput) -> str:
    """Detect every disk on a Kirby-Bauer plate photo, measure each inhibition zone in mm,
    and classify S/I/SDD/R against CLSI M100-Ed33 once antibiotics are assigned.

    Calibration uses the 90 mm plate rim. Disk identity is not read from the photo: pass
    `antibiotics` (clockwise from 12 o'clock) or `panel`; bundled synthetic samples carry
    their known layout. Unassigned disks stay UNKNOWN. Measurements the pipeline does not
    trust carry flags (e.g. overlap, low_circularity) and are excluded from expert rules.

    Returns a table with position, antibiotic, zone diameter, category and notes, plus an
    `analysis_id` used by bacterioscope_update_plate and bacterioscope_review_plate.
    Sessions expire after 48 newer analyses.
    """
    path = (_image_file(params.image_path) if params.image_path
            else _session_call(plate_session.sample_path, params.sample_id))
    payload = await anyio.to_thread.run_sync(
        lambda: _session_call(plate_session.analyze_path, path, params.sample_id)
    )
    analysis_id = payload["analysis_id"]
    session = plate_session.get_session(analysis_id)
    labels = session.labels
    if params.antibiotics is not None:
        labels = _labels_by_position(session.order, params.antibiotics)
    elif params.panel is not None:
        labels = _session_call(plate_session.panel_labels, analysis_id, params.panel)
    session.labels = list(labels)
    samples = plate_session.samples()
    extra = {
        "source": params.sample_id or path.name,
        "synthetic_sample": bool(params.sample_id and samples[params.sample_id]["synthetic"]),
        "disks_detected": len(session.order),
        "px_per_mm": round(payload["calibration"]["px_per_mm"], 3),
        "traceability": payload["traceability"],
    }
    return _plate_response(analysis_id, params.response_format, extra)


class UpdatePlateInput(BaseModel):
    """Changes to an analyzed plate, addressed by clockwise position."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    analysis_id: str = Field(min_length=8, max_length=64, description="From analyze_plate.")
    assignments: dict[int, str | None] = Field(
        default_factory=dict,
        description="Position -> antibiotic name or code (null unassigns), e.g. {\"1\": \"CIP\"}.",
    )
    corrections: dict[int, float] = Field(
        default_factory=dict,
        description="Position -> corrected zone diameter in mm (above 0, up to 90). "
        "Corrections block the agent review until cleared.",
    )
    clear_corrections: bool = Field(default=False, description="Drop all diameter corrections.")
    panel: str | None = Field(default=None, max_length=80, description="Reassign by panel.")
    response_format: ResponseFormat = _FORMAT_FIELD


def _position_map(order: list[int], keyed: dict[int, Any]) -> dict[int, Any]:
    bad = [p for p in keyed if not 1 <= p <= len(order)]
    if bad:
        raise ToolError(f"Positions {bad} do not exist; this plate has {len(order)} disks.")
    return {order[p - 1]: value for p, value in keyed.items()}


@mcp.tool(
    name="bacterioscope_update_plate",
    annotations=ToolAnnotations(
        title="Assign antibiotics or correct zones", readOnlyHint=False,
        destructiveHint=False, idempotentHint=True, openWorldHint=False,
    ),
)
async def bacterioscope_update_plate(params: UpdatePlateInput) -> str:
    """Assign antibiotics to disks, apply a panel, or correct zone diameters on an analyzed
    plate, then return every disk reclassified.

    Use when the reader identified the printed disk codes, or a measured zone is wrong.
    A manual correction is traced (measured value kept) and blocks
    bacterioscope_review_plate until `clear_corrections` is set, because the report cannot
    yet trace a corrected diameter.
    """
    session = _session_call(plate_session.get_session, params.analysis_id)
    labels = list(session.labels)
    if params.panel is not None:
        labels = _session_call(plate_session.panel_labels, params.analysis_id, params.panel)
    for index, name in _position_map(session.order, params.assignments).items():
        labels[index] = _resolve_antibiotic(name) if name else None
    overrides = {} if params.clear_corrections else dict(session.overrides)
    overrides.update(_position_map(session.order, params.corrections))
    _session_call(plate_session.classify, params.analysis_id, labels, overrides)
    extra = {"corrections": len(overrides), "review_blocked": bool(overrides)}
    return _plate_response(params.analysis_id, params.response_format, extra)


class ReviewPlateInput(BaseModel):
    """Inputs for the grounded agent review."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    analysis_id: str = Field(min_length=8, max_length=64, description="From analyze_plate.")
    organism: str = Field(
        default="Escherichia coli", min_length=1, max_length=120,
        description="Identified organism, e.g. 'Klebsiella pneumoniae'.",
    )
    include_public_alerts: bool = Field(
        default=False,
        description="Search official INS (Colombia) and OPS/PAHO alerts via Tavily (external).",
    )
    response_format: ResponseFormat = _FORMAT_FIELD


def _review_markdown(outcome: dict[str, Any], order: list[int]) -> str:
    report = outcome["report"]
    lines = [f"# Review `{report.get('analysis_id', '')}`", f"- status: {outcome['status']}"]
    if outcome.get("fallback_reason"):
        lines.append(f"- fallback reason: {outcome['fallback_reason']} "
                     "(the deterministic report below is complete)")
    if report.get("model_explanation"):
        lines += ["", report["model_explanation"]]
    lines += ["", "| Pos | Antibiotic | Zone (mm) | Category | In rules |", "|---|---|---|---|---|"]
    position = {index: pos for pos, index in enumerate(order, start=1)}
    observations = sorted(report["measurement"]["observations"],
                          key=lambda obs: position.get(obs["disk_index"], 0))
    for obs in observations:
        lines.append(
            f"| {position.get(obs['disk_index'], '?')} | {obs['antibiotic_code']} "
            f"| {obs['zone_mm']:.1f} | {obs['category']} "
            f"| {'yes' if obs['included_in_rule_evaluation'] else 'no'} |"
        )
    catalog = report.get("catalog_status") or {}
    lines += ["", "Rule coverage: " + ", ".join(f"{k}={v}" for k, v in catalog.items())]
    lines.append(f"Alert search: {report.get('alert_search_status', 'not_requested')}")
    for alert in report.get("public_alerts") or []:
        source = str(alert.get("source", "")).upper()
        lines.append(f"- [{source}] {alert.get('title')} {alert.get('url')}")
    lines += ["", DISCLAIMER]
    return "\n".join(lines)


@mcp.tool(
    name="bacterioscope_review_plate",
    annotations=ToolAnnotations(
        title="Grounded Nemotron review", readOnlyHint=True, destructiveHint=False,
        idempotentHint=False, openWorldHint=True,
    ),
)
async def bacterioscope_review_plate(params: ReviewPlateInput) -> str:
    """Run the grounded agent review of an analyzed plate: deterministic CLSI results,
    rule-catalog coverage, optional INS/OPS public alerts, and a Nemotron narrative
    (Nebius Token Factory) validated against the evidence it cites.

    Without NEBIUS_API_KEY, or if the model output fails validation, status is 'fallback'
    and the deterministic report is still complete. Fails while manual corrections exist.
    Makes billable model calls when a key is configured.
    """
    session = _session_call(plate_session.get_session, params.analysis_id)
    outcome = await anyio.to_thread.run_sync(
        lambda: _session_call(plate_session.review, params.analysis_id, params.organism,
                              params.include_public_alerts)
    )
    if params.response_format == ResponseFormat.JSON:
        return json.dumps(outcome, indent=2, default=str)
    return _review_markdown(outcome, session.order)


class ClassifyZoneInput(BaseModel):
    """One zone diameter to classify."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    antibiotic: str = Field(min_length=2, max_length=60, description="Name or code, e.g. 'MEM'.")
    diameter_mm: float = Field(gt=0, le=90, description="Inhibition zone diameter in mm.")


@mcp.tool(
    name="bacterioscope_classify_zone",
    annotations=ToolAnnotations(
        title="Classify one zone diameter", readOnlyHint=True, destructiveHint=False,
        idempotentHint=True, openWorldHint=False,
    ),
)
async def bacterioscope_classify_zone(params: ClassifyZoneInput) -> str:
    """Classify a single zone diameter as S, SDD, I or R for Enterobacterales under
    CLSI M100-Ed33, without any photo. Whole-mm criteria use nearest-mm rounding.

    Returns JSON: antibiotic, diameter_mm, whole_mm, category, breakpoints,
    near_breakpoint (within 2 mm of an edge) and the standard.
    """
    key = _resolve_antibiotic(params.antibiotic)
    result = CLSIClassifier().classify(key, params.diameter_mm)
    return json.dumps({
        "antibiotic": key, "code": CODES.get(key), "diameter_mm": params.diameter_mm,
        "whole_mm": math.floor(params.diameter_mm + 0.5), "category": result.category,
        "breakpoints": result.breakpoints,
        "near_breakpoint": _near_breakpoint(params.diameter_mm, result.breakpoints),
        "standard": CLSI_EDITION,
    }, indent=2)


class BreakpointsInput(BaseModel):
    """Optional filter for the breakpoint table."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    antibiotic: str | None = Field(default=None, max_length=60, description="Name or code.")
    response_format: ResponseFormat = _FORMAT_FIELD


def _range(low: float | None, high: float | None) -> str:
    return f"{low:g}-{high:g}" if low is not None and high is not None else "-"


@mcp.tool(
    name="bacterioscope_get_breakpoints",
    annotations=ToolAnnotations(
        title="CLSI zone breakpoints", readOnlyHint=True, destructiveHint=False,
        idempotentHint=True, openWorldHint=False,
    ),
)
async def bacterioscope_get_breakpoints(params: BreakpointsInput) -> str:
    """List the CLSI M100-Ed33 Enterobacterales zone-diameter breakpoints (mm) used by
    BacterioScope: S if >= S, R if <= R, I or SDD in the range between. Filter by one
    antibiotic (name or code) or omit it for all 15.
    """
    keys = [_resolve_antibiotic(params.antibiotic)] if params.antibiotic else sorted(
        CLSI_2023_ENTEROBACTERIACEAE)
    table = {key: CLSI_2023_ENTEROBACTERIACEAE[key] for key in keys}
    if params.response_format == ResponseFormat.JSON:
        return json.dumps({"standard": CLSI_EDITION, "breakpoints": table}, indent=2)
    lines = [f"# Zone breakpoints, {CLSI_EDITION}", "",
             "| Antibiotic | Code | S >= | I | SDD | R <= |", "|---|---|---|---|---|---|"]
    for key, bp in table.items():
        lines.append(
            f"| {key} | {CODES.get(key, '-')} | {bp['S']:g} | "
            f"{_range(bp.get('I_low'), bp.get('I_high'))} | "
            f"{_range(bp.get('SDD_low'), bp.get('SDD_high'))} | {bp['R']:g} |"
        )
    return "\n".join(lines)


@mcp.tool(
    name="bacterioscope_list_samples",
    annotations=ToolAnnotations(
        title="List bundled sample plates", readOnlyHint=True, destructiveHint=False,
        idempotentHint=True, openWorldHint=False,
    ),
)
async def bacterioscope_list_samples() -> str:
    """List the bundled sample plates usable as `sample_id` in bacterioscope_analyze_plate.

    Synthetic samples are generated plates with a known antibiotic layout (assigned
    automatically); real samples are clinical photos with no assignment. Returns JSON.
    """
    counts = plate_session.synthetic_disk_counts()
    return json.dumps([
        {"sample_id": sample_id, "synthetic": info["synthetic"],
         "disks": counts.get(sample_id)}
        for sample_id, info in plate_session.samples().items()
    ], indent=2)


@mcp.tool(
    name="bacterioscope_list_panels",
    annotations=ToolAnnotations(
        title="List fixed disk panels", readOnlyHint=True, destructiveHint=False,
        idempotentHint=True, openWorldHint=False,
    ),
)
async def bacterioscope_list_panels() -> str:
    """List the fixed antibiotic panels usable as `panel`, each with its antibiotics in
    clockwise order from 12 o'clock. A panel applies only when its size equals the
    detected disk count. Returns JSON.
    """
    manager = PanelManager()
    panels = []
    for name in manager.list_panels():
        config = manager.load(name)
        panels.append({"panel": name, "standard": config.standard,
                       "organism_group": config.organism_group,
                       "antibiotics": config.antibiotics})
    return json.dumps(panels, indent=2)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(plate_session.REPO_ROOT / ".env")


def main() -> None:
    """Start the server over stdio (default) or streamable HTTP on localhost."""
    parser = argparse.ArgumentParser(description="BacterioScope MCP server")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    _load_env()
    if args.transport == "streamable-http":
        mcp.settings.host = "127.0.0.1"
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
