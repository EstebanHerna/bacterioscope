"""Streamlit interactive demo for BacterioScope.

Run with:
    streamlit run src/bacterioscope/app.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, NamedTuple, cast

import cv2
import numpy as np
import streamlit as st
from numpy.typing import NDArray

from bacterioscope._app_logic import (
    _ANTIBIOTIC_OPTIONS,
    _UNASSIGNED,
    reclassify_with_override,
)
from bacterioscope.classification.clsi import CLSIClassifier, SusceptibilityResult
from bacterioscope.evaluation.plate_report import generate_plate_html
from bacterioscope.panels.manager import PanelManager
from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline, PipelineConfig
from bacterioscope.utils.visualization import draw_results

_EXAMPLE_IMAGE = Path(__file__).parent.parent.parent / "docs" / "plate_original.png"

# ---------------------------------------------------------------------------
# Design tokens — single source of truth for CSS variables
# ---------------------------------------------------------------------------
_CSS = """
<style>
:root {
  --bg:      #0f0f0f;
  --surf:    #171717;
  --border:  #252525;
  --text:    #e0e0e0;
  --text2:   #6a6a6a;
  --text3:   #333333;
  --s:       #4d9e6a;
  --i:       #c48a2e;
  --r:       #b54040;
  --flag:    #a07830;
}

.main .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1280px; }

/* Header */
.bs-h1 { font-size:1.35rem; font-weight:700; letter-spacing:-.025em; color:var(--text); }
.bs-sub { font-size:.74rem; color:var(--text2); margin-top:3px; }

/* Section label */
.bs-sec {
  font-size:.60rem; font-weight:600; text-transform:uppercase;
  letter-spacing:.10em; color:var(--text3); margin-bottom:9px;
}

/* Mode indicator */
.bs-mode {
  padding:9px 11px; border:1px solid var(--border);
  border-left:2px solid var(--text3); border-radius:4px; margin-bottom:12px;
}
.bs-mode--ok  { border-left-color:var(--s); }
.bs-mode--geo { border-left-color:var(--i); }
.mode-title { font-size:.75rem; font-weight:600; color:var(--text); }
.mode-desc  { font-size:.70rem; color:var(--text2); margin-top:2px; line-height:1.5; }

/* Metric cards */
.bs-metrics { display:flex; gap:6px; margin-bottom:13px; }
.bs-metric {
  flex:1; padding:11px 10px; border:1px solid var(--border);
  border-radius:4px; background:var(--surf);
}
.m-n { font-size:2rem; font-weight:700; letter-spacing:-.02em;
        font-variant-numeric:tabular-nums; line-height:1; }
.bs-metric--s .m-n { color:var(--s); }
.bs-metric--i .m-n { color:var(--i); }
.bs-metric--r .m-n { color:var(--r); }
.m-lbl { font-size:.60rem; font-weight:600; text-transform:uppercase;
          letter-spacing:.08em; color:var(--text3); margin-top:5px; }

/* Table */
.bs-table { width:100%; border-collapse:collapse; font-size:.81rem; }
.bs-table thead tr { border-bottom:1px solid var(--border); }
.bs-table th {
  text-align:left; padding:0 10px 8px;
  font-size:.60rem; font-weight:600; text-transform:uppercase;
  letter-spacing:.09em; color:var(--text3);
}
.bs-table th:last-child { text-align:right; }
.bs-table tbody tr { border-bottom:1px solid var(--border); }
.bs-table td { padding:8px 10px; vertical-align:middle; }
.col-name { color:var(--text); font-weight:500; }
.col-diam { color:var(--text2); font-variant-numeric:tabular-nums; }
.col-cat  { text-align:right; }

/* Badges */
.bs-badge {
  display:inline-block; padding:2px 7px; border-radius:3px;
  font-size:.67rem; font-weight:600; letter-spacing:.04em;
}
.bs-badge--s       { background:rgba(77,158,106,.10); color:var(--s); }
.bs-badge--i       { background:rgba(196,138,46,.10); color:var(--i); }
.bs-badge--r       { background:rgba(181,64,64,.10);  color:var(--r); }
.bs-badge--unknown { background:rgba(100,100,100,.10); color:var(--text2); }
.bs-badge--manual  { background:rgba(160,120,48,.08); color:var(--flag);
                     font-size:.58rem; margin-left:4px; }
.bs-badge--flag    { background:rgba(160,120,48,.08); color:var(--flag);
                     font-size:.58rem; margin-left:4px; }

/* Caption / helper */
.bs-cap { font-size:.68rem; color:var(--text3); margin-top:5px;
          font-variant-numeric:tabular-nums; }

/* Divider */
.bs-hr { border:none; border-top:1px solid var(--border); margin:11px 0; }

/* Sidebar */
.bs-sb-brand {
  font-size:.88rem; font-weight:700; letter-spacing:-.01em;
  color:var(--text); padding-bottom:13px; margin-bottom:13px;
  border-bottom:1px solid var(--border);
}
.bs-sb-v { font-size:.63rem; font-weight:400; color:var(--text3); margin-left:4px; }
.bs-sb-sec {
  font-size:.60rem; font-weight:600; text-transform:uppercase;
  letter-spacing:.09em; color:var(--text3); margin-bottom:9px;
}
.bs-sb-hr { border:none; border-top:1px solid var(--border); margin:13px 0; }
.bs-sb-refs { font-size:.68rem; color:var(--text3); line-height:1.85; }

/* Welcome */
.bs-welcome {
  display:flex; flex-direction:column; align-items:center;
  text-align:center; padding:60px 20px; color:var(--text3);
}
.w-title { font-size:.85rem; font-weight:500; color:var(--text2); margin-bottom:5px; }
.w-desc  { font-size:.73rem; line-height:1.7; max-width:310px; }

/* Upload hint */
.bs-upload-hint { font-size:.69rem; color:var(--text3); margin-top:4px; }

/* Hough table */
.bs-th {
  font-size:.60rem; font-weight:600; text-transform:uppercase;
  letter-spacing:.09em; color:var(--text3); padding-bottom:7px;
}
.bs-td { padding-top:7px; font-size:.80rem; color:var(--text2);
          font-variant-numeric:tabular-nums; }
.bs-td-name { padding-top:7px; font-size:.80rem; color:var(--text); }
.bs-td-badge { padding-top:7px; text-align:right; }

@media (prefers-color-scheme: light) {
  :root {
    --bg:     #f7f7f5;
    --surf:   #ffffff;
    --border: #e0e0e0;
    --text:   #111111;
    --text2:  #666666;
    --text3:  #aaaaaa;
  }
}
</style>
"""

# ---------------------------------------------------------------------------
# Stroke-colour presets — None means use category colour
# ---------------------------------------------------------------------------
_STROKE_OPTIONS: dict[str, tuple[int, int, int] | None] = {
    "Category (S/I/R)": None,
    "White": (240, 240, 240),
    "Cyan": (220, 210, 0),
    "Amber": (30, 130, 200),
}


class _VisConfig(NamedTuple):
    show_mode: str           # "Annotated" | "Original" | "Blend"
    opacity: float           # 0.0–1.0, relevant only in Blend mode
    stroke_color: tuple[int, int, int] | None


# ---------------------------------------------------------------------------
# Cached pipeline factory
# ---------------------------------------------------------------------------
@st.cache_resource
def _build_pipeline(plate_mm: float, organism: str) -> BacterioScopePipeline:
    return BacterioScopePipeline(
        PipelineConfig(plate_diameter_mm=plate_mm, organism_group=organism)
    )


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------
def _assignment_key(i: int) -> str:
    return f"bs_antibiotic_{i}"


def _override_key(i: int) -> str:
    return f"bs_override_{i}"


def _sync_for_new_image(image_id: str) -> None:
    if st.session_state.get("bs_image_id") == image_id:
        return
    st.session_state["bs_image_id"] = image_id
    st.session_state.pop("bs_result", None)
    stale = [k for k in st.session_state
             if k.startswith("bs_antibiotic_") or k.startswith("bs_override_")]
    for k in stale:
        del st.session_state[k]


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------
def _run_pipeline(
    pipeline: BacterioScopePipeline, uploaded: Any
) -> AnalysisResult | None:
    if "bs_result" in st.session_state:
        return cast(AnalysisResult, st.session_state["bs_result"])
    suffix = Path(uploaded.name).suffix.lower() or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(uploaded.read())
        tmp_path = Path(tmp.name)
    try:
        with st.spinner("Analyzing..."):
            result = pipeline.analyze(tmp_path)
        st.session_state["bs_result"] = result
        return result
    except (ValueError, FileNotFoundError) as exc:
        st.error(f"Analysis failed: {exc}")
        return None
    finally:
        tmp_path.unlink(missing_ok=True)


def _run_pipeline_from_path(
    pipeline: BacterioScopePipeline, image_path: Path
) -> AnalysisResult | None:
    if "bs_result" in st.session_state:
        return cast(AnalysisResult, st.session_state["bs_result"])
    try:
        with st.spinner("Analyzing..."):
            result = pipeline.analyze(image_path)
        st.session_state["bs_result"] = result
        return result
    except (ValueError, FileNotFoundError) as exc:
        st.error(f"Analysis failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def _sidebar() -> tuple[float, str, str | None]:
    st.sidebar.markdown(
        '<div class="bs-sb-brand">BacterioScope<span class="bs-sb-v">v0.1</span></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="bs-sb-sec">Configuration</div>', unsafe_allow_html=True)
    plate_mm = st.sidebar.number_input(
        "Plate diameter (mm)", min_value=50.0, max_value=150.0, value=90.0, step=1.0
    )
    organism = st.sidebar.selectbox("Organism group", options=["Enterobacteriaceae"], index=0)
    st.sidebar.markdown('<hr class="bs-sb-hr">', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="bs-sb-sec">Disk Assignment</div>', unsafe_allow_html=True)
    pm = PanelManager()
    panel_opts = ["Manual"] + pm.list_panels()
    panel_sel = st.sidebar.selectbox(
        "Mode", panel_opts,
        help="Manual: assign antibiotics per disk. Panel: auto-assign by angular position."
    )
    panel_name = None if str(panel_sel) == "Manual" else str(panel_sel)
    st.sidebar.markdown('<hr class="bs-sb-hr">', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="bs-sb-refs">CLSI M100-Ed33 (2023)<br>ISO 20776-2</div>',
                        unsafe_allow_html=True)
    return float(plate_mm), str(organism), panel_name


def _vis_sidebar() -> _VisConfig:
    st.sidebar.markdown('<hr class="bs-sb-hr">', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="bs-sb-sec">Visualization</div>', unsafe_allow_html=True)
    show_mode = st.sidebar.radio(
        "Image", ["Annotated", "Blend", "Original"],
        horizontal=True, label_visibility="collapsed",
    )
    opacity = 0.75
    if show_mode == "Blend":
        opacity = float(st.sidebar.slider("Overlay opacity", 0.0, 1.0, 0.75, 0.05))
    stroke_label = st.sidebar.selectbox(
        "Stroke colour", list(_STROKE_OPTIONS.keys()), label_visibility="visible"
    )
    return _VisConfig(
        show_mode=str(show_mode),
        opacity=opacity,
        stroke_color=_STROKE_OPTIONS[str(stroke_label)],
    )


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def _is_hough_mode(result: AnalysisResult) -> bool:
    if not result.disks:
        return True
    return result.disks[0].confidence == 0.0


def _mode_indicator(is_hough: bool) -> None:
    if is_hough:
        css = "bs-mode bs-mode--geo"
        title = "Geometric detection (Hough circles)"
        desc = (
            "No YOLOv8 weights found. Zone diameters are measured. "
            "Assign antibiotics below to compute S/I/R."
        )
    else:
        css = "bs-mode bs-mode--ok"
        title = "YOLOv8 model active"
        desc = "Disk identification and zone measurement are fully automated."
    st.markdown(
        f'<div class="{css}"><div class="mode-title">{title}</div>'
        f'<div class="mode-desc">{desc}</div></div>',
        unsafe_allow_html=True,
    )


def _category_badge(category: str) -> str:
    css = category.lower() if category in ("S", "I", "R") else "unknown"
    return f'<span class="bs-badge bs-badge--{css}">{category}</span>'


def _flag_badges(disk_flags: list[str]) -> str:
    labels = {
        "low_circularity": "irregular",
        "small_zone": "small",
        "boundary": "edge",
        "overlap": "overlap",
    }
    return "".join(
        f'<span class="bs-badge bs-badge--flag">{labels.get(f, f)}</span>'
        for f in disk_flags
    )


def _metric_cards(classifications: list[SusceptibilityResult]) -> None:
    counts = {k: sum(1 for c in classifications if c.category == k) for k in ("S", "I", "R")}
    labels = {"S": "Susceptible", "I": "Intermediate", "R": "Resistant"}
    cards = "".join(
        f'<div class="bs-metric bs-metric--{cat.lower()}">'
        f'<div class="m-n">{counts[cat]}</div>'
        f'<div class="m-lbl">{labels[cat]}</div>'
        f"</div>"
        for cat in ("S", "I", "R")
    )
    st.markdown(f'<div class="bs-metrics">{cards}</div>', unsafe_allow_html=True)


def _compose_image(
    result: AnalysisResult,
    vis: _VisConfig,
) -> NDArray[np.uint8]:
    """Build the display image based on current visualisation settings."""
    original = result.original_image
    if vis.show_mode == "Original" and original is not None:
        return original

    base = original.copy() if original is not None else np.zeros((100, 100, 3), dtype=np.uint8)
    annotated = draw_results(
        base, result.disks, result.zones, result.classifications,
        result.flags or None, vis.stroke_color,
    )

    if vis.show_mode == "Blend" and original is not None and vis.opacity < 1.0:
        return cv2.addWeighted(original, 1.0 - vis.opacity, annotated, vis.opacity, 0)
    return annotated


def _effective_classifications(
    result: AnalysisResult,
    classifier: CLSIClassifier,
    panel_labels: list[str] | None = None,
) -> list[SusceptibilityResult]:
    if not _is_hough_mode(result):
        return result.classifications
    effective = []
    for i, zone in enumerate(result.zones):
        if panel_labels is not None and i < len(panel_labels):
            chosen = panel_labels[i]
        else:
            chosen = st.session_state.get(_assignment_key(i), _UNASSIGNED)
        raw_override = st.session_state.get(_override_key(i))
        override_mm = float(raw_override) if raw_override is not None else None
        cls, _ = reclassify_with_override(
            zone.diameter_mm, override_mm, chosen, classifier, result.disks[i].label
        )
        effective.append(cls)
    return effective


def _results_table(
    classifications: list[SusceptibilityResult],
    flags: list[list[str]],
) -> None:
    if not classifications:
        st.markdown(
            '<div class="w-title">No disks detected</div>'
            '<div class="w-desc">Try a higher-contrast image with clearly visible halos.</div>',
            unsafe_allow_html=True,
        )
        return
    rows = "".join(
        f"<tr>"
        f'<td class="col-name">{c.antibiotic}'
        f'{_flag_badges(flags[i] if i < len(flags) else [])}</td>'
        f'<td class="col-diam">{c.zone_diameter_mm:.1f} mm</td>'
        f'<td class="col-cat">{_category_badge(c.category)}</td>'
        f"</tr>"
        for i, c in enumerate(classifications)
    )
    st.markdown(
        '<table class="bs-table"><thead><tr>'
        '<th>Antibiotic</th><th>Zone</th><th>Category</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>',
        unsafe_allow_html=True,
    )


def _hough_table(
    result: AnalysisResult,
    effective: list[SusceptibilityResult],
    panel_labels: list[str] | None = None,
) -> None:
    if not result.zones:
        st.markdown(
            '<div class="w-title">No disks detected</div>'
            '<div class="w-desc">Try a higher-contrast image with clearly visible halos.</div>',
            unsafe_allow_html=True,
        )
        return
    h1, h2, h3, h4, h5 = st.columns([1, 2, 2, 5, 2])
    h1.markdown('<div class="bs-th">Disk</div>', unsafe_allow_html=True)
    h2.markdown('<div class="bs-th">Measured</div>', unsafe_allow_html=True)
    h3.markdown('<div class="bs-th">Override</div>', unsafe_allow_html=True)
    h4.markdown('<div class="bs-th">Antibiotic</div>', unsafe_allow_html=True)
    h5.markdown('<div class="bs-th">Category</div>', unsafe_allow_html=True)
    st.markdown('<hr class="bs-hr" style="margin:2px 0 4px">', unsafe_allow_html=True)
    for i, zone in enumerate(result.zones):
        disk_flags = result.flags[i] if i < len(result.flags) else []
        flag_html = _flag_badges(disk_flags)
        c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 5, 2])
        c1.markdown(
            f'<div class="bs-td-name">{result.disks[i].label}{flag_html}</div>',
            unsafe_allow_html=True,
        )
        c2.markdown(
            f'<div class="bs-td">{zone.diameter_mm:.1f} mm</div>', unsafe_allow_html=True
        )
        raw_override = c3.number_input(
            f"ov_{i}", min_value=0.0, max_value=80.0,
            value=float(st.session_state.get(_override_key(i), zone.diameter_mm)),
            step=0.5, format="%.1f", label_visibility="collapsed", key=_override_key(i),
        )
        is_manual = abs(float(raw_override) - zone.diameter_mm) > 0.01
        if panel_labels is not None and i < len(panel_labels):
            c4.markdown(
                f'<div class="bs-td-name">{panel_labels[i]}'
                '<span class="bs-badge bs-badge--manual" style="margin-left:6px">panel</span>'
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            c4.selectbox(
                f"ab_{i}", _ANTIBIOTIC_OPTIONS, key=_assignment_key(i),
                label_visibility="collapsed",
            )
        badge = _category_badge(effective[i].category)
        manual_tag = '<span class="bs-badge bs-badge--manual">manual</span>' if is_manual else ""
        c5.markdown(
            f'<div class="bs-td-badge">{badge}{manual_tag}</div>', unsafe_allow_html=True
        )


def _download_button(
    result: AnalysisResult, classifications: list[SusceptibilityResult]
) -> None:
    import dataclasses
    display = dataclasses.replace(result, classifications=classifications)
    html = generate_plate_html(display)
    st.download_button(
        "Download HTML report", html.encode(), "bacterioscope_report.html", "text/html"
    )


def _show_results(
    result: AnalysisResult,
    classifier: CLSIClassifier,
    vis: _VisConfig,
    panel_labels: list[str] | None = None,
) -> None:
    col_img, col_data = st.columns([10, 9], gap="large")
    is_hough = _is_hough_mode(result)
    effective = _effective_classifications(result, classifier, panel_labels)
    with col_img:
        st.markdown('<div class="bs-sec">Plate</div>', unsafe_allow_html=True)
        display_img = _compose_image(result, vis)
        st.image(cv2.cvtColor(display_img, cv2.COLOR_BGR2RGB), use_container_width=True)
        st.markdown(
            f'<div class="bs-cap">{result.px_per_mm:.2f} px/mm &nbsp;·&nbsp;'
            f" {result.plate_diameter_px:.0f} px plate</div>",
            unsafe_allow_html=True,
        )
    with col_data:
        st.markdown('<div class="bs-sec">Classification</div>', unsafe_allow_html=True)
        _mode_indicator(is_hough)
        _metric_cards(effective)
        if result.zones:
            st.markdown('<hr class="bs-hr">', unsafe_allow_html=True)
        if is_hough:
            _hough_table(result, effective, panel_labels)
        else:
            _results_table(result.classifications, result.flags or [])
        if result.zones:
            _download_button(result, effective)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(
        page_title="BacterioScope", layout="wide", initial_sidebar_state="expanded"
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="bs-h1">BacterioScope</div>'
        '<div class="bs-sub">Kirby-Bauer analysis — CLSI M100-Ed33 (2023)</div>',
        unsafe_allow_html=True,
    )

    plate_mm, organism, panel_name = _sidebar()
    vis = _vis_sidebar()
    pipeline = _build_pipeline(plate_mm, organism)

    col_up, col_ex = st.columns([4, 1])
    with col_up:
        uploaded = st.file_uploader(
            "plate", type=["jpg", "jpeg", "png", "bmp", "tiff"],
            label_visibility="collapsed",
        )
    with col_ex:
        use_example = st.button("Use example image", use_container_width=True)

    st.markdown(
        '<div class="bs-upload-hint">'
        "Upload a raw, unprocessed plate photograph (JPEG, PNG, TIFF).</div>",
        unsafe_allow_html=True,
    )

    if use_example and _EXAMPLE_IMAGE.exists():
        _sync_for_new_image("__example__")
        result = _run_pipeline_from_path(pipeline, _EXAMPLE_IMAGE)
    elif uploaded is not None:
        _sync_for_new_image(f"{uploaded.name}:{uploaded.size}")
        result = _run_pipeline(pipeline, uploaded)
    else:
        st.markdown(
            '<div class="bs-welcome">'
            '<div class="w-title">Upload a plate photograph to begin</div>'
            '<div class="w-desc">Use an unprocessed image directly from the camera, '
            "or click 'Use example image'.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    if result is None:
        return

    panel_labels: list[str] | None = None
    if panel_name is not None:
        pm = PanelManager()
        try:
            panel_cfg = pm.load(panel_name)
            assigned = pm.assign(result.disks, panel_cfg, result.plate_center)
            if assigned is None:
                st.warning(
                    f"Panel '{panel_name}' has {len(panel_cfg.antibiotics)} disks "
                    f"but {len(result.disks)} detected. Using manual assignment."
                )
            else:
                panel_labels = assigned
        except FileNotFoundError as exc:
            st.error(str(exc))

    _show_results(result, pipeline.classifier, vis, panel_labels)


if __name__ == "__main__":
    main()
