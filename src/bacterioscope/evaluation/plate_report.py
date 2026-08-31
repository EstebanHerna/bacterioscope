"""Per-plate HTML report generation for BacterioScope analysis results.

Generates a self-contained HTML report that embeds the annotated plate image
as a base64 PNG, includes the per-disk results table with quality flags,
calibration metadata, and a professional-confirmation disclaimer.

The HTML report includes print CSS so it produces a clean PDF when printed
from any browser (Ctrl+P / Cmd+P, then Save as PDF).
"""

from __future__ import annotations

import base64
import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy.typing as npt

if TYPE_CHECKING:
    from bacterioscope.pipeline import AnalysisResult

_DISCLAIMER = (
    "BacterioScope is a decision-support tool. Results must be reviewed and "
    "confirmed by a qualified microbiology professional before guiding clinical "
    "treatment decisions. This output is not a validated medical device report."
)

_CSS = (
    "body{font-family:sans-serif;max-width:900px;margin:2em auto;padding:0 1.2em;color:#222}"
    "h1{font-size:1.4em;border-bottom:2px solid #333;padding-bottom:.3em}"
    "h2{font-size:1.1em;border-bottom:1px solid #ddd;margin-top:1.5em}"
    "table{border-collapse:collapse;width:100%;margin:1em 0}"
    "th,td{border:1px solid #ccc;padding:.4em .8em;text-align:left;font-size:.9em}"
    "th{background:#f5f5f5;font-weight:600}"
    ".S{color:#1a7a2e;font-weight:600}.I{color:#7a5c00;font-weight:600}"
    ".R{color:#8a1010;font-weight:600}"
    ".flag{display:inline-block;background:#f0a000;color:#fff;font-size:.75em;"
    "border-radius:3px;padding:1px 5px;margin:1px}"
    ".disclaimer{background:#fef3cd;border:1px solid #f0c040;border-radius:4px;"
    "padding:.8em 1em;font-size:.85em;margin:1.5em 0}"
    ".meta{font-size:.85em;color:#555;margin:.3em 0}"
    "img{max-width:100%;border:1px solid #ddd;margin:.5em 0}"
    "@media print{body{max-width:100%}}"
)


def _image_to_b64(image: npt.NDArray[Any]) -> str:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode()


def _category_cell(cat: str) -> str:
    css = cat if cat in ("S", "I", "R") else ""
    return f'<td class="{css}">{cat}</td>'


def _flags_cell(flags: list[str]) -> str:
    if not flags:
        return "<td></td>"
    badges = "".join(f'<span class="flag">{f}</span>' for f in flags)
    return f"<td>{badges}</td>"


def _build_rows(result: AnalysisResult) -> str:
    rows = []
    for i, cls in enumerate(result.classifications):
        disk_flags = result.flags[i] if i < len(result.flags) else []
        rows.append(
            f"<tr><td>{i + 1}</td><td>{cls.antibiotic}</td>"
            f"<td>{cls.zone_diameter_mm:.1f}</td>"
            f"{_category_cell(cls.category)}"
            f"{_flags_cell(disk_flags)}</tr>"
        )
    return "".join(rows)


def generate_plate_html(
    result: AnalysisResult,
    analysis_time: datetime.datetime | None = None,
) -> str:
    """Generate a self-contained HTML report for one plate analysis.

    Args:
        result: Completed AnalysisResult from BacterioScopePipeline.analyze().
        analysis_time: Timestamp shown in the report. Defaults to now (UTC).

    Returns:
        Standalone HTML string with the annotated image embedded as base64.
    """
    ts = (analysis_time or datetime.datetime.now(datetime.timezone.utc)).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    img_src = (
        result.annotated_image if result.annotated_image is not None else result.original_image
    )
    img_html = ""
    if img_src is not None:
        b64 = _image_to_b64(img_src)
        if b64:
            img_html = f'<img src="data:image/png;base64,{b64}" alt="Annotated plate">'

    table = (
        "<table><thead><tr>"
        "<th>#</th><th>Antibiotic</th><th>Zone (mm)</th><th>Category</th><th>Flags</th>"
        f"</tr></thead><tbody>{_build_rows(result)}</tbody></table>"
    )

    return (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        "<meta charset='utf-8'>\n<title>BacterioScope Report</title>\n"
        f"<style>{_CSS}</style>\n</head>\n<body>\n"
        "<h1>BacterioScope Analysis Report</h1>\n"
        f'<p class="meta">Image: {result.image_path}</p>\n'
        f'<p class="meta">Analyzed: {ts} &nbsp;|&nbsp; '
        f"Calibration: {result.px_per_mm:.2f} px/mm &nbsp;|&nbsp; "
        f"Disks detected: {len(result.disks)}</p>\n"
        f'<div class="disclaimer">{_DISCLAIMER}</div>\n'
        f"<h2>Annotated Plate</h2>\n{img_html}\n"
        f"<h2>Results</h2>\n{table}\n"
        "</body>\n</html>"
    )


def save_plate_report(result: AnalysisResult, output_path: Path) -> None:
    """Write the plate HTML report to a file.

    Args:
        result: Completed AnalysisResult from BacterioScopePipeline.analyze().
        output_path: Destination file path (should end in .html).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_plate_html(result), encoding="utf-8")
