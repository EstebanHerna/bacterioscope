"""Per-plate HTML report — 9-section scientific report for BacterioScope.

Sections
--------
1. Header: analysis ID, timestamp
2. Clinical disclaimer
3. Calibration metadata
4. Annotated plate image with scale bar
5. Per-disk thumbnail strip
6. Results table: zone, category, breakpoints, last-line flag
7. Provenance: SHA-256, commit, software version, breakpoint table
8. Machine-readable JSON appendix
9. Print CSS
"""

from __future__ import annotations

import base64
import datetime
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import numpy.typing as npt

from bacterioscope.classification.clsi import LAST_LINE_ANTIBIOTICS
from bacterioscope.design.tokens import FONT_STACK_MONO, FONT_STACK_SANS, palette

if TYPE_CHECKING:
    from bacterioscope.pipeline import AnalysisResult

_DISCLAIMER = (
    "BacterioScope is a decision-support tool. Results must be reviewed and "
    "confirmed by a qualified microbiology professional before guiding clinical "
    "treatment decisions. This output is not a validated medical device report."
)

_SCALE_BAR_MM = 20


def _palette_props(p: dict[str, str]) -> str:
    return "".join(f"--bs-{k.replace('_', '-')}:{v};" for k, v in p.items())


def _css_block() -> str:
    lp = _palette_props(palette("light"))
    dp = _palette_props(palette("dark"))
    fonts = (
        f"--bs-font-sans:{FONT_STACK_SANS};"
        f"--bs-font-mono:{FONT_STACK_MONO};"
    )
    tokens = (
        f":root{{{lp}{fonts}}}"
        "@media(prefers-color-scheme:dark)"
        f"{{:root:not([data-theme=light]){{{dp}}}}}"
        f"[data-theme=dark]{{{dp}}}"
    )
    components = (
        "body{font-family:var(--bs-font-sans);background:var(--bs-bg-base);"
        "color:var(--bs-text-primary);max-width:900px;margin:2em auto;"
        "padding:0 1.2em}"
        "h1{font-size:1.4em;border-bottom:2px solid var(--bs-border);"
        "padding-bottom:.3em}"
        "h2{font-size:1.1em;border-bottom:1px solid var(--bs-border);"
        "margin-top:1.5em}"
        "table{border-collapse:collapse;width:100%;margin:1em 0}"
        "th,td{border:1px solid var(--bs-border);"
        "padding:.4em .8em;text-align:left;font-size:.9em}"
        "th{background:var(--bs-bg-raised);font-weight:600}"
        ".S{color:var(--bs-cat-susceptible);font-weight:600}"
        ".I{color:var(--bs-cat-intermediate);font-weight:600}"
        ".R{color:var(--bs-cat-resistant);font-weight:600}"
        ".flag{display:inline-block;background:var(--bs-quality-warning);"
        "color:var(--bs-bg-base);font-size:.75em;border-radius:3px;"
        "padding:1px 5px;margin:1px}"
        ".disclaimer{background:var(--bs-bg-surface);"
        "border:1px solid var(--bs-signal);border-radius:4px;"
        "padding:.8em 1em;font-size:.85em;margin:1.5em 0}"
        ".meta{font-size:.85em;color:var(--bs-text-secondary);margin:.3em 0}"
        ".prov{font-family:var(--bs-font-mono);font-size:.78em;"
        "word-break:break-all}"
        ".scale-bar{display:flex;align-items:center;gap:.4em;margin:.3em 0;"
        "font-size:.8em;color:var(--bs-text-secondary)}"
        ".scale-line{height:3px;background:var(--bs-text-primary);"
        "display:inline-block}"
        ".disk-strip{display:flex;gap:.5em;flex-wrap:wrap;margin:.5em 0}"
        ".disk-thumb{text-align:center;font-size:.75em;"
        "color:var(--bs-text-secondary)}"
        ".disk-thumb img{display:block;border:1px solid var(--bs-border);"
        "border-radius:3px;width:64px;height:64px;object-fit:cover}"
        "img.plate{max-width:100%;border:1px solid var(--bs-border);"
        "margin:.5em 0}"
        "details summary{cursor:pointer;color:var(--bs-signal)}"
        "details pre{background:var(--bs-bg-raised);padding:.8em;"
        "font-size:.8em;overflow-x:auto;border-radius:4px;"
        "font-family:var(--bs-font-mono)}"
        ".ll{font-size:.7em;background:var(--bs-cat-resistant);"
        "color:var(--bs-bg-base);border-radius:3px;"
        "padding:0 4px;margin-left:3px;vertical-align:middle}"
        "@media print{body{max-width:100%}}"
    )
    return tokens + components


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


def _crop_disk_roi(
    image: npt.NDArray[Any],
    cx: int,
    cy: int,
    radius_px: int,
    size: int = 64,
) -> npt.NDArray[Any]:
    h, w = image.shape[:2]
    pad = max(int(radius_px * 2), 10)
    x1, y1 = max(0, cx - pad), max(0, cy - pad)
    x2, y2 = min(w, cx + pad), min(h, cy + pad)
    roi = image[y1:y2, x1:x2]
    if roi.size == 0:
        return np.zeros((size, size, 3), dtype=np.uint8)
    return cv2.resize(roi, (size, size))


def _disk_thumb_html(
    image: npt.NDArray[Any],
    cx: int,
    cy: int,
    radius_px: int,
    label: str,
    category: str,
) -> str:
    thumb = _crop_disk_roi(image, cx, cy, radius_px)
    ok, buf = cv2.imencode(".png", thumb)
    if not ok:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode()
    css = category if category in ("S", "I", "R") else ""
    cap = f'<span class="{css}">{label}</span>'
    return (
        f'<div class="disk-thumb">'
        f'<img src="data:image/png;base64,{b64}" alt="{label}">'
        f"{cap}</div>"
    )


def _section_disk_strip(result: AnalysisResult) -> str:
    image = result.original_image if result.original_image is not None else result.annotated_image
    if image is None or not result.disks:
        return ""
    thumbs = []
    for i, disk in enumerate(result.disks):
        cat = result.classifications[i].category if i < len(result.classifications) else "?"
        html = _disk_thumb_html(
            image, disk.center_x, disk.center_y, int(disk.radius_px), disk.label, cat
        )
        if html:
            thumbs.append(html)
    if not thumbs:
        return ""
    return f'<h2>Disk Strip</h2>\n<div class="disk-strip">\n{"".join(thumbs)}\n</div>\n'


def _last_line_badge(antibiotic: str) -> str:
    if antibiotic.lower() in LAST_LINE_ANTIBIOTICS:
        return '<span class="ll">last-line</span>'
    return ""


def _build_rows(result: AnalysisResult) -> str:
    rows = []
    for i, cls in enumerate(result.classifications):
        disk_flags = result.flags[i] if i < len(result.flags) else []
        bp = cls.breakpoints
        bp_str = f"S≥{bp.get('S', '-')} R≤{bp.get('R', '-')}" if bp else ""
        badge = _last_line_badge(cls.antibiotic)
        rows.append(
            f"<tr><td>{i + 1}</td>"
            f"<td>{cls.antibiotic}{badge}</td>"
            f"<td>{cls.zone_diameter_mm:.1f}</td>"
            f"{_category_cell(cls.category)}"
            f"<td>{bp_str}</td>"
            f"{_flags_cell(disk_flags)}</tr>"
        )
    return "".join(rows)


def _section_plate_image(result: AnalysisResult) -> str:
    img_src = (
        result.annotated_image if result.annotated_image is not None else result.original_image
    )
    img_html = ""
    if img_src is not None:
        b64 = _image_to_b64(img_src)
        if b64:
            img_html = (
                f'<img class="plate" src="data:image/png;base64,{b64}"'
                f' alt="Annotated plate">'
            )
    note = f"1&nbsp;mm&nbsp;=&nbsp;{result.px_per_mm:.2f}&nbsp;px in source image"
    scale_bar = (
        f'<div class="scale-bar">'
        f'<span class="scale-line" style="width:80px"></span>'
        f'<span>{_SCALE_BAR_MM} mm reference&nbsp;({note})</span>'
        f'</div>'
    )
    return f"<h2>Annotated Plate</h2>\n{img_html}\n{scale_bar}\n"


def _section_calibration(result: AnalysisResult) -> str:
    items = [
        ("Image", result.image_path),
        ("Plate diameter", f"{result.plate_diameter_px:.0f} px"),
        ("Calibration", f"{result.px_per_mm:.3f} px/mm"),
        ("Disks detected", str(len(result.disks))),
    ]
    parts = "".join(f'<p class="meta"><strong>{k}:</strong> {v}</p>' for k, v in items)
    return f"<h2>Calibration</h2>\n{parts}\n"


def _section_results_table(result: AnalysisResult) -> str:
    header = (
        "<th>#</th><th>Antibiotic</th><th>Zone (mm)</th>"
        "<th>Category</th><th>Breakpoints</th><th>Flags</th>"
    )
    table = (
        f"<table><thead><tr>{header}</tr></thead>"
        f"<tbody>{_build_rows(result)}</tbody></table>"
    )
    return f"<h2>Results</h2>\n{table}\n"


def _section_provenance(result: AnalysisResult) -> str:
    fields = [
        ("Analysis ID", result.analysis_id),
        ("Software Version", result.software_version or "—"),
        ("Commit Hash", result.commit_hash),
        ("Breakpoint Table", result.breakpoint_table_version or "—"),
        ("Image SHA-256", result.image_sha256 or "not computed"),
    ]
    rows = "".join(
        f'<tr><th>{k}</th><td class="prov">{v}</td></tr>' for k, v in fields
    )
    return f"<h2>Provenance</h2>\n<table><tbody>{rows}</tbody></table>\n"


def _section_json(result: AnalysisResult) -> str:
    json_str = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    return (
        "<h2>Machine-Readable Data</h2>\n"
        "<details><summary>Show JSON</summary>\n"
        f"<pre>{json_str}</pre>\n"
        "</details>\n"
    )


def generate_plate_html(
    result: AnalysisResult,
    analysis_time: datetime.datetime | None = None,
) -> str:
    """Generate a 9-section self-contained HTML report for one plate analysis.

    Args:
        result: Completed AnalysisResult from BacterioScopePipeline.analyze().
        analysis_time: Timestamp shown in the report. Defaults to now (UTC).

    Returns:
        Standalone HTML string with embedded images and provenance data.
    """
    ts = (analysis_time or datetime.datetime.now(datetime.timezone.utc)).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    aid = result.analysis_id[:8] + "…" if result.analysis_id else ""
    header = (
        "<h1>BacterioScope Analysis Report</h1>\n"
        f'<p class="meta">ID: {aid}'
        f" | Analyzed: {ts}</p>\n"
    )
    body = "\n".join([
        header,
        f'<div class="disclaimer">{_DISCLAIMER}</div>',
        _section_calibration(result),
        _section_plate_image(result),
        _section_disk_strip(result),
        _section_results_table(result),
        _section_provenance(result),
        _section_json(result),
    ])
    return (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        "<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        "<title>BacterioScope Report</title>\n"
        f"<style>{_css_block()}</style>\n"
        f"</head>\n<body>\n{body}\n</body>\n</html>"
    )


def save_plate_report(result: AnalysisResult, output_path: Path) -> None:
    """Write the plate HTML report to a file.

    Args:
        result: Completed AnalysisResult from BacterioScopePipeline.analyze().
        output_path: Destination file path (should end in .html).
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generate_plate_html(result), encoding="utf-8")
