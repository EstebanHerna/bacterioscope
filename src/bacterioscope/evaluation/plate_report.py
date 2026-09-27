"""Per-plate HTML report — 9-section scientific report for BacterioScope.

Sections
--------
1. Header: analysis ID, timestamp
2. Clinical disclaimer
3. Calibration metadata (stat tiles)
4. Annotated plate image with scale bar
5. Per-disk thumbnail strip
6. Results table: zone, category, breakpoints, last-line flag
7. Provenance: SHA-256, commit, software version, breakpoint table
8. Machine-readable JSON appendix
9. Print CSS

Layout and color come from the Clinical Slate design system
(``bacterioscope.design.tokens``): the same palette, type scale and spacing
grid used across the project, not a one-off style for this report.
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
from bacterioscope.design.tokens import (
    FONT_STACK_MONO,
    FONT_STACK_SANS,
    RADIUS_CONTAINER,
    RADIUS_CONTROL,
    SPACE,
    palette,
)

if TYPE_CHECKING:
    from bacterioscope.pipeline import AnalysisResult

_DISCLAIMER = (
    "BacterioScope is a decision-support tool. Results must be reviewed and "
    "confirmed by a qualified microbiology professional before guiding clinical "
    "treatment decisions. This output is not a validated medical device report."
)

_SCALE_BAR_MM = 20
_SCALE_BAR_MIN_PX = 60
_SCALE_BAR_MAX_PX = 220
_DISK_THUMB_PX = 112


def _palette_props(p: dict[str, str]) -> str:
    return "".join(f"--bs-{k.replace('_', '-')}:{v};" for k, v in p.items())


def _space_props() -> str:
    return "".join(f"--bs-space-{k}:{v}px;" for k, v in SPACE.items())


def _css_tokens() -> str:
    lp = _palette_props(palette("light"))
    dp = _palette_props(palette("dark"))
    fonts = f"--bs-font-sans:{FONT_STACK_SANS};--bs-font-mono:{FONT_STACK_MONO};"
    layout = (
        f"{_space_props()}"
        f"--bs-radius-container:{RADIUS_CONTAINER}px;"
        f"--bs-radius-control:{RADIUS_CONTROL}px;"
    )
    return (
        f":root{{{lp}{fonts}{layout}}}"
        "@media(prefers-color-scheme:dark)"
        f"{{:root:not([data-theme=light]){{{dp}}}}}"
        f"[data-theme=dark]{{{dp}}}"
    )


def _css_page() -> str:
    return (
        "*{box-sizing:border-box}"
        "body{font-family:var(--bs-font-sans);font-size:15px;line-height:1.5;"
        "background:var(--bs-bg-base);color:var(--bs-text-primary);"
        "max-width:920px;margin:0 auto;"
        "padding:var(--bs-space-3xl) var(--bs-space-xl)}"
        ".eyebrow{font-size:12px;font-weight:600;letter-spacing:.08em;"
        "text-transform:uppercase;color:var(--bs-signal);"
        "margin:0 0 var(--bs-space-xs)}"
        "h1{font-size:28px;font-weight:600;letter-spacing:-.01em;"
        "margin:0 0 var(--bs-space-sm)}"
        ".meta-line{font-size:14px;color:var(--bs-text-secondary);"
        "margin:0 0 var(--bs-space-xl);font-variant-numeric:tabular-nums}"
        "h2{font-size:18px;font-weight:600;"
        "margin:var(--bs-space-2xl) 0 var(--bs-space-md);"
        "padding-bottom:var(--bs-space-xs);"
        "border-bottom:1px solid var(--bs-border)}"
        ".disclaimer{background:var(--bs-bg-surface);"
        "border:1px solid var(--bs-border);"
        "border-left:3px solid var(--bs-signal);"
        "border-radius:var(--bs-radius-container);"
        "padding:var(--bs-space-md) var(--bs-space-lg);"
        "font-size:14px;color:var(--bs-text-secondary)}"
    )


def _css_stats() -> str:
    return (
        ".stat-grid{display:grid;"
        "grid-template-columns:repeat(auto-fit,minmax(140px,1fr));"
        "gap:var(--bs-space-md);margin:var(--bs-space-lg) 0}"
        ".stat{background:var(--bs-bg-surface);"
        "border:1px solid var(--bs-border);"
        "border-radius:var(--bs-radius-container);"
        "padding:var(--bs-space-md) var(--bs-space-lg)}"
        ".stat .label{font-size:12px;text-transform:uppercase;"
        "letter-spacing:.06em;color:var(--bs-text-secondary);margin:0 0 4px}"
        ".stat .value{font-family:var(--bs-font-mono);font-size:22px;"
        "font-variant-numeric:tabular-nums;color:var(--bs-text-primary)}"
    )


def _css_plate_image() -> str:
    return (
        "img.plate{display:block;width:100%;border:1px solid var(--bs-border);"
        "border-radius:var(--bs-radius-container)}"
        ".plate-figure{margin:var(--bs-space-md) 0}"
        ".scale-bar{display:flex;align-items:center;gap:var(--bs-space-sm);"
        "margin-top:var(--bs-space-sm);font-family:var(--bs-font-mono);"
        "font-size:13px;color:var(--bs-text-secondary)}"
        ".ruler{position:relative;height:9px;flex:none}"
        ".ruler .bar{position:absolute;left:0;right:0;top:4px;height:1px;"
        "background:var(--bs-text-secondary)}"
        ".ruler .tick{position:absolute;top:0;bottom:0;width:1px;"
        "background:var(--bs-text-secondary)}"
        ".ruler .tick.start{left:0}"
        ".ruler .tick.end{right:0}"
        ".scale-note{font-size:11px;color:var(--bs-text-secondary);"
        "opacity:.8;margin:var(--bs-space-xs) 0 0}"
    )


def _css_disk_strip() -> str:
    return (
        ".disk-strip{display:grid;"
        "grid-template-columns:repeat(auto-fill,minmax(88px,1fr));"
        "gap:var(--bs-space-sm);margin:var(--bs-space-md) 0}"
        ".disk-thumb{text-align:center;font-size:12px;"
        "color:var(--bs-text-secondary)}"
        ".disk-thumb img{display:block;width:100%;aspect-ratio:1;"
        "object-fit:cover;border:1px solid var(--bs-border);"
        "border-radius:var(--bs-radius-control);margin-bottom:4px}"
        ".disk-thumb .mm{display:block;font-family:var(--bs-font-mono);"
        "font-variant-numeric:tabular-nums;color:var(--bs-text-primary);"
        "font-size:12px;margin-bottom:2px}"
    )


def _css_table() -> str:
    return (
        "table{border-collapse:collapse;width:100%;"
        "margin:var(--bs-space-md) 0;font-size:14px}"
        "th,td{border-bottom:1px solid var(--bs-border);"
        "padding:var(--bs-space-sm) var(--bs-space-md);text-align:left}"
        "th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;"
        "color:var(--bs-text-secondary);font-weight:600}"
        "td:nth-child(3){font-family:var(--bs-font-mono);"
        "font-variant-numeric:tabular-nums}"
        "tbody tr:hover{background:var(--bs-bg-surface)}"
        ".badge{display:inline-flex;align-items:center;justify-content:center;"
        "min-width:18px;padding:1px 7px;border-radius:var(--bs-radius-control);"
        "font-size:12px;font-weight:600;border:1px solid currentColor}"
        ".badge.S{color:var(--bs-cat-susceptible)}"
        ".badge.I{color:var(--bs-cat-intermediate)}"
        ".badge.R{color:var(--bs-cat-resistant)}"
        ".flag{display:inline-block;background:var(--bs-bg-raised);"
        "border:1px solid var(--bs-quality-warning);"
        "color:var(--bs-quality-warning);font-size:11px;"
        "border-radius:var(--bs-radius-control);padding:1px 6px;"
        "margin:1px 3px 1px 0}"
        ".ll{font-size:10px;text-transform:uppercase;letter-spacing:.04em;"
        "background:var(--bs-cat-resistant);color:var(--bs-bg-base);"
        "border-radius:var(--bs-radius-control);padding:1px 5px;"
        "margin-left:5px;vertical-align:middle}"
    )


def _css_provenance_and_misc() -> str:
    return (
        "dl.provenance{display:grid;"
        "grid-template-columns:max-content 1fr;"
        "gap:var(--bs-space-xs) var(--bs-space-lg);"
        "margin:var(--bs-space-md) 0;font-size:13px}"
        "dl.provenance dt{color:var(--bs-text-secondary)}"
        "dl.provenance dd{margin:0;font-family:var(--bs-font-mono);"
        "word-break:break-all;color:var(--bs-text-primary)}"
        "details{margin:var(--bs-space-md) 0}"
        "details summary{cursor:pointer;color:var(--bs-signal);"
        "font-size:13px;font-weight:600}"
        "details pre{background:var(--bs-bg-raised);"
        "border:1px solid var(--bs-border);"
        "border-radius:var(--bs-radius-container);"
        "padding:var(--bs-space-md);margin-top:var(--bs-space-sm);"
        "font-size:12px;font-family:var(--bs-font-mono);overflow-x:auto}"
        "footer{margin-top:var(--bs-space-2xl);"
        "padding-top:var(--bs-space-md);"
        "border-top:1px solid var(--bs-border);"
        "font-size:12px;color:var(--bs-text-secondary)}"
        "@media print{"
        "body{max-width:100%;background:#fff;color:#101619;padding:0}"
        ".stat,.disclaimer{border-color:#ccc}"
        "details:not([open]) pre{display:none}"
        "a{color:inherit}"
        "}"
    )


def _css_block() -> str:
    return (
        _css_tokens()
        + _css_page()
        + _css_stats()
        + _css_plate_image()
        + _css_disk_strip()
        + _css_table()
        + _css_provenance_and_misc()
    )


def _image_to_b64(image: npt.NDArray[Any]) -> str:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        return ""
    return base64.b64encode(buf.tobytes()).decode()


def _category_cell(cat: str) -> str:
    if cat not in ("S", "I", "R"):
        return f"<td>{cat}</td>"
    return f'<td><span class="badge {cat}">{cat}</span></td>'


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


def _stat_tile(label: str, value: str) -> str:
    return f'<div class="stat"><p class="label">{label}</p><p class="value">{value}</p></div>'


def _scale_bar_width_px(px_per_mm: float) -> int:
    raw = round(_SCALE_BAR_MM * px_per_mm) if px_per_mm > 0 else _SCALE_BAR_MIN_PX
    return max(_SCALE_BAR_MIN_PX, min(_SCALE_BAR_MAX_PX, raw))


def _ruler_html(width_px: int) -> str:
    return (
        f'<span class="ruler" style="width:{width_px}px">'
        '<span class="bar"></span>'
        '<span class="tick start"></span>'
        '<span class="tick end"></span>'
        "</span>"
    )


def _disk_thumb_html(
    image: npt.NDArray[Any],
    cx: int,
    cy: int,
    radius_px: int,
    label: str,
    category: str,
    diameter_mm: float,
) -> str:
    thumb = _crop_disk_roi(image, cx, cy, radius_px, size=_DISK_THUMB_PX)
    ok, buf = cv2.imencode(".png", thumb)
    if not ok:
        return ""
    b64 = base64.b64encode(buf.tobytes()).decode()
    is_sir = category in ("S", "I", "R")
    badge = f'<span class="badge {category}">{label}</span>' if is_sir else label
    return (
        '<div class="disk-thumb">'
        f'<img src="data:image/png;base64,{b64}" alt="{label}">'
        f'<span class="mm">{diameter_mm:.1f} mm</span>'
        f"{badge}</div>"
    )


def _section_disk_strip(result: AnalysisResult) -> str:
    image = result.original_image if result.original_image is not None else result.annotated_image
    if image is None or not result.disks:
        return ""
    thumbs = []
    for i, disk in enumerate(result.disks):
        cat = result.classifications[i].category if i < len(result.classifications) else "?"
        mm = result.zones[i].diameter_mm if i < len(result.zones) else 0.0
        html = _disk_thumb_html(
            image, disk.center_x, disk.center_y, int(disk.radius_px), disk.label, cat, mm
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
    width_px = _scale_bar_width_px(result.px_per_mm)
    scale_bar = (
        '<div class="scale-bar">'
        f"{_ruler_html(width_px)}"
        f"<span>{_SCALE_BAR_MM}&nbsp;mm reference &mdash; "
        f"{result.px_per_mm:.2f} px/mm in source image</span>"
        "</div>"
        '<p class="scale-note">Reference only: on-screen size depends on your '
        "browser's zoom and the image's responsive scaling.</p>"
    )
    figure = f'<div class="plate-figure">\n{img_html}\n{scale_bar}\n</div>\n'
    return f"<h2>Annotated Plate</h2>\n{figure}"


def _section_calibration(result: AnalysisResult) -> str:
    tiles = "".join([
        _stat_tile("Plate diameter", f"{result.plate_diameter_px:.0f} px"),
        _stat_tile("Calibration", f"{result.px_per_mm:.2f} px/mm"),
        _stat_tile("Disks detected", str(len(result.disks))),
    ])
    return f'<h2>Calibration</h2>\n<div class="stat-grid">{tiles}</div>\n'


def _section_results_table(result: AnalysisResult) -> str:
    header = (
        "<th>#</th><th>Antibiotic</th><th>Zone (mm)</th>"
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
    rows = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in fields)
    return f'<h2>Provenance</h2>\n<dl class="provenance">{rows}</dl>\n'


def _section_json(result: AnalysisResult) -> str:
    json_str = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    return (
        "<h2>Machine-Readable Data</h2>\n"
        "<details><summary>Show JSON</summary>\n"
        f"<pre>{json_str}</pre>\n"
        "</details>\n"
    )


def _footer_html(result: AnalysisResult) -> str:
    version = result.software_version or "dev"
    bp = result.breakpoint_table_version or "unspecified"
    return (
        "<footer>"
        f"BacterioScope {version} &middot; {bp} &middot; "
        "Generated locally, no data leaves this machine."
        "</footer>"
    )


def _header_html(ts: str, aid: str) -> str:
    return (
        '<p class="eyebrow">BacterioScope</p>\n'
        "<h1>Plate Analysis Report</h1>\n"
        f'<p class="meta-line">Analysis {aid} &middot; {ts}</p>\n'
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
    body = "\n".join([
        _header_html(ts, aid),
        f'<div class="disclaimer">{_DISCLAIMER}</div>',
        _section_calibration(result),
        _section_plate_image(result),
        _section_disk_strip(result),
        _section_results_table(result),
        _section_provenance(result),
        _section_json(result),
        _footer_html(result),
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
