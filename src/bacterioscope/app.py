"""Streamlit interactive demo for BacterioScope.

Run with:
    streamlit run src/bacterioscope/app.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import cv2
import streamlit as st

from bacterioscope._app_logic import (
    _ANTIBIOTIC_OPTIONS,
    _UNASSIGNED,
    reclassify_with_assignment,
)
from bacterioscope.classification.clsi import CLSIClassifier, SusceptibilityResult
from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline, PipelineConfig

_PLATE_SVG = (
    '<svg width="80" height="80" viewBox="0 0 80 80" fill="none"'
    ' xmlns="http://www.w3.org/2000/svg">'
    '<circle cx="40" cy="40" r="37" stroke="rgba(255,255,255,0.07)" stroke-width="2"/>'
    '<circle cx="40" cy="40" r="27" stroke="rgba(255,255,255,0.04)"'
    ' stroke-width="1" stroke-dasharray="3 4"/>'
    '<circle cx="40" cy="20" r="4.5" fill="rgba(255,255,255,0.07)"/>'
    '<circle cx="57" cy="30" r="4.5" fill="rgba(255,255,255,0.07)"/>'
    '<circle cx="57" cy="50" r="4.5" fill="rgba(255,255,255,0.07)"/>'
    '<circle cx="40" cy="60" r="4.5" fill="rgba(255,255,255,0.07)"/>'
    '<circle cx="23" cy="50" r="4.5" fill="rgba(255,255,255,0.07)"/>'
    '<circle cx="23" cy="30" r="4.5" fill="rgba(255,255,255,0.07)"/>'
    '</svg>'
)

_CSS = """
<style>
/* ---- Layout ---- */
.main .block-container {
  padding-top: 1.5rem;
  padding-bottom: 2rem;
  max-width: 1320px;
}

/* ---- Upload zone ---- */
[data-testid="stFileUploadDropzone"] {
  border: 1px dashed rgba(74,127,212,0.28) !important;
  border-radius: 8px !important;
  background: rgba(59,130,246,0.02) !important;
  transition: border-color 200ms ease, background 200ms ease !important;
}
[data-testid="stFileUploadDropzone"]:hover {
  border-color: rgba(74,127,212,0.52) !important;
  background: rgba(59,130,246,0.05) !important;
}

/* ---- Animation ---- */
@keyframes bs-in {
  from { opacity: 0; transform: translateY(4px); }
  to   { opacity: 1; transform: translateY(0);   }
}
.bs-panel { animation: bs-in 200ms cubic-bezier(0.23,1,0.32,1) both; }

/* ---- Header ---- */
.bs-header { margin-bottom: 22px; }
.bs-header-title {
  font-size: 1.65rem;
  font-weight: 700;
  letter-spacing: -0.025em;
  color: #eef1f7;
  line-height: 1.1;
}
.bs-header-sub {
  font-size: 0.79rem;
  color: #4a5570;
  margin-top: 5px;
}
.bs-upload-hint { font-size: 0.72rem; color: #3a4560; margin-top: 6px; margin-bottom: 4px; }

/* ---- Section label ---- */
.bs-label {
  font-size: 0.66rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.10em;
  color: #3a4560;
  margin-bottom: 10px;
}

/* ---- Caption ---- */
.bs-cap { font-size: 0.71rem; color: #3a4560; margin-top: 8px; font-variant-numeric: tabular-nums; }

/* ---- Mode indicator ---- */
.bs-mode {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  background: rgba(10,15,30,0.7);
  border: 1px solid rgba(59,130,246,0.15);
  border-left: 3px solid #3455a0;
  border-radius: 9px;
  padding: 12px 14px;
  margin-bottom: 15px;
  animation: bs-in 200ms cubic-bezier(0.23,1,0.32,1) both;
}
.bs-mode--ok {
  border-left-color: #22a060;
  border-color: rgba(34,192,96,0.15);
}
.bs-mode .dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: #3b82f6; margin-top: 5px; flex-shrink: 0;
  box-shadow: 0 0 8px rgba(59,130,246,0.55);
}
.bs-mode--ok .dot { background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.55); }
.mode-title { font-size: 0.79rem; font-weight: 600; color: #c0d0e8; line-height: 1.3; }
.mode-desc { font-size: 0.75rem; color: #6a7a96; line-height: 1.6; margin-top: 3px; }

/* ---- Metric cards ---- */
.bs-metrics { display: flex; gap: 8px; margin-bottom: 16px; }
.bs-metric {
  flex: 1;
  padding: 16px 14px 12px;
  border-radius: 10px;
  border: 1px solid transparent;
  position: relative;
  overflow: hidden;
}
.bs-metric--s { background: rgba(34,197,94,0.08); border-color: rgba(34,197,94,0.18); }
.bs-metric--i { background: rgba(245,158,11,0.08); border-color: rgba(245,158,11,0.18); }
.bs-metric--r { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.18); }

.m-n {
  font-size: 2.5rem; font-weight: 800; line-height: 1;
  letter-spacing: -0.03em; font-variant-numeric: tabular-nums;
}
.bs-metric--s .m-n { color: #4ade80; }
.bs-metric--i .m-n { color: #fbbf24; }
.bs-metric--r .m-n { color: #f87171; }

.m-track {
  height: 3px; background: rgba(255,255,255,0.07);
  border-radius: 2px; margin: 9px 0 7px; overflow: hidden;
}
.m-fill { height: 100%; border-radius: 2px; transition: width 700ms cubic-bezier(0.23,1,0.32,1); }
.bs-metric--s .m-fill { background: #4ade80; }
.bs-metric--i .m-fill { background: #fbbf24; }
.bs-metric--r .m-fill { background: #f87171; }

.m-lbl {
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.08em; opacity: 0.5;
}
.bs-metric--s .m-lbl { color: #4ade80; }
.bs-metric--i .m-lbl { color: #fbbf24; }
.bs-metric--r .m-lbl { color: #f87171; }

/* ---- Divider ---- */
.bs-hr { border: none; border-top: 1px solid rgba(255,255,255,0.055); margin: 16px 0; }

/* ---- Static results table (YOLOv8 mode) ---- */
.bs-table { width: 100%; border-collapse: collapse; font-size: 0.845rem; }
.bs-table thead tr { border-bottom: 1px solid rgba(255,255,255,0.055); }
.bs-table th {
  text-align: left; padding: 0 12px 9px;
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.09em; color: #3a4560;
}
.bs-table th:last-child { text-align: right; }
.bs-table tbody tr {
  opacity: 0;
  animation: bs-in 175ms cubic-bezier(0.23,1,0.32,1) forwards;
  border-bottom: 1px solid rgba(255,255,255,0.032);
  transition: background 140ms ease;
}
.bs-table tbody tr:hover { background: rgba(255,255,255,0.028); }
.bs-table tbody tr:nth-child(1) { animation-delay: 40ms; }
.bs-table tbody tr:nth-child(2) { animation-delay: 80ms; }
.bs-table tbody tr:nth-child(3) { animation-delay: 120ms; }
.bs-table tbody tr:nth-child(4) { animation-delay: 160ms; }
.bs-table tbody tr:nth-child(5) { animation-delay: 200ms; }
.bs-table tbody tr:nth-child(6) { animation-delay: 240ms; }
.bs-table tbody tr:nth-child(7) { animation-delay: 280ms; }
.bs-table tbody tr:nth-child(8) { animation-delay: 320ms; }
.bs-table td { padding: 10px 12px; vertical-align: middle; }
.col-name { color: #c0cce0; font-weight: 500; }
.col-diam { color: #5a6a80; font-variant-numeric: tabular-nums; }
.col-cat  { text-align: right; }

/* ---- Hough assignment table ---- */
.bs-th {
  font-size: 0.65rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.09em; color: #3a4560; padding-bottom: 8px;
}
.bs-td {
  padding-top: 8px; font-size: 0.82rem; color: #5a6a80;
  font-variant-numeric: tabular-nums;
}
.bs-td-badge { padding-top: 8px; text-align: right; }

/* ---- Badge ---- */
.bs-badge {
  display: inline-block; padding: 3px 10px; border-radius: 5px;
  font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em;
  border: 1px solid transparent;
}
.bs-badge--s { background: rgba(34,197,94,0.1); color: #4ade80;
               border-color: rgba(34,197,94,0.22); }
.bs-badge--i { background: rgba(245,158,11,0.1); color: #fbbf24;
               border-color: rgba(245,158,11,0.22); }
.bs-badge--r { background: rgba(239,68,68,0.1); color: #f87171;
               border-color: rgba(239,68,68,0.22); }
.bs-badge--unknown { background: rgba(80,90,110,0.12); color: #5a6a80;
                     border-color: rgba(80,90,110,0.2); }

/* ---- Welcome / empty states ---- */
.bs-welcome, .bs-empty {
  display: flex; flex-direction: column; align-items: center;
  text-align: center; color: #3a4560;
}
.bs-welcome { padding: 56px 20px; }
.bs-empty   { padding: 32px 16px; }
.bs-welcome svg, .bs-empty svg { margin-bottom: 16px; }
.w-title, .e-title {
  font-weight: 600; color: #6a7a90; margin-bottom: 7px;
}
.w-title { font-size: 0.95rem; }
.e-title { font-size: 0.87rem; }
.w-desc, .e-desc {
  font-size: 0.78rem; line-height: 1.7; max-width: 340px;
}

/* ---- Sidebar ---- */
.bs-sb-brand {
  font-size: 0.95rem; font-weight: 700; letter-spacing: -0.01em;
  color: #dde4f0; padding-bottom: 16px; margin-bottom: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.bs-sb-v { font-size: 0.68rem; font-weight: 500; color: #3a4560; margin-left: 5px; }
.bs-sb-sec {
  font-size: 0.64rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.09em; color: #3a4560; margin-bottom: 12px;
}
.bs-sb-hr { border: none; border-top: 1px solid rgba(255,255,255,0.055); margin: 18px 0 14px; }
.bs-sb-refs { font-size: 0.71rem; color: #3a4560; line-height: 1.9; }

@media (prefers-reduced-motion: reduce) {
  .bs-panel, .bs-mode, .bs-table tbody tr { animation: none; opacity: 1; }
  .m-fill { transition: none; }
}
</style>
"""


@st.cache_resource
def _build_pipeline(plate_mm: float, organism: str) -> BacterioScopePipeline:
    return BacterioScopePipeline(
        PipelineConfig(plate_diameter_mm=plate_mm, organism_group=organism)
    )



def _assignment_key(i: int) -> str:
    return f"bs_antibiotic_{i}"


def _sync_for_new_image(image_id: str) -> None:
    if st.session_state.get("bs_image_id") == image_id:
        return
    st.session_state["bs_image_id"] = image_id
    st.session_state.pop("bs_result", None)
    stale = [k for k in st.session_state if k.startswith("bs_antibiotic_")]
    for k in stale:
        del st.session_state[k]


def _run_pipeline(
    pipeline: BacterioScopePipeline, uploaded: Any
) -> AnalysisResult | None:
    if "bs_result" in st.session_state:
        result: AnalysisResult = st.session_state["bs_result"]
        return result
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


def _sidebar() -> tuple[float, str]:
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
    st.sidebar.markdown(
        '<div class="bs-sb-refs">CLSI M100-Ed33 (2023)<br>ISO 20776-2</div>',
        unsafe_allow_html=True,
    )
    return float(plate_mm), str(organism)


def _is_hough_mode(result: AnalysisResult) -> bool:
    if not result.classifications:
        return True
    return any(c.antibiotic.startswith("disk_") for c in result.classifications)


def _mode_indicator(is_hough: bool) -> None:
    if is_hough:
        cls, title = "bs-mode", "Geometric detection mode (Hough circles)"
        desc = (
            "Antibiotic identification requires the trained YOLOv8 model (Phase 1). "
            "Zone diameters are measured. Assign antibiotics below to compute S/I/R."
        )
    else:
        cls, title = "bs-mode bs-mode--ok", "YOLOv8 model active"
        desc = "Disk identification and zone measurement are fully automated."
    st.markdown(
        f'<div class="{cls}"><div class="dot"></div>'
        f'<div><div class="mode-title">{title}</div>'
        f'<div class="mode-desc">{desc}</div></div></div>',
        unsafe_allow_html=True,
    )


def _category_badge(category: str) -> str:
    css = category.lower() if category in ("S", "I", "R") else "unknown"
    return f'<span class="bs-badge bs-badge--{css}">{category}</span>'


def _metric_cards(classifications: list[SusceptibilityResult]) -> None:
    total = len(classifications) or 1
    counts = {k: sum(1 for c in classifications if c.category == k) for k in ("S", "I", "R")}
    labels = {"S": "Susceptible", "I": "Intermediate", "R": "Resistant"}
    cards = "".join(
        f'<div class="bs-metric bs-metric--{cat.lower()}">'
        f'<div class="m-n">{counts[cat]}</div>'
        f'<div class="m-track"><div class="m-fill" style="width:{counts[cat]/total*100:.0f}%">'
        f'</div></div>'
        f'<div class="m-lbl">{labels[cat]}</div>'
        f"</div>"
        for cat in ("S", "I", "R")
    )
    st.markdown(f'<div class="bs-metrics">{cards}</div>', unsafe_allow_html=True)


def _effective_classifications(
    result: AnalysisResult,
    classifier: CLSIClassifier,
) -> list[SusceptibilityResult]:
    if not _is_hough_mode(result):
        return result.classifications
    effective = []
    for i, zone in enumerate(result.zones):
        chosen = st.session_state.get(_assignment_key(i), _UNASSIGNED)
        effective.append(
            reclassify_with_assignment(
                zone.diameter_mm, chosen, classifier, result.disks[i].label
            )
        )
    return effective


def _results_table(classifications: list[SusceptibilityResult]) -> None:
    if not classifications:
        st.markdown(
            f'<div class="bs-empty">{_PLATE_SVG}'
            '<div class="e-title">No antibiotic disks detected</div>'
            '<div class="e-desc">The pipeline did not find paper disks in this image. '
            "Try a higher-contrast raw plate photograph with clearly visible disk halos.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return
    rows = "".join(
        f"<tr>"
        f'<td class="col-name">{c.antibiotic}</td>'
        f'<td class="col-diam">{c.zone_diameter_mm:.1f} mm</td>'
        f'<td class="col-cat">{_category_badge(c.category)}</td>'
        f"</tr>"
        for c in classifications
    )
    st.markdown(
        '<table class="bs-table"><thead><tr>'
        '<th>Antibiotic</th><th>Zone</th><th>Category</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>',
        unsafe_allow_html=True,
    )


def _hough_table(result: AnalysisResult, effective: list[SusceptibilityResult]) -> None:
    if not result.zones:
        st.markdown(
            f'<div class="bs-empty">{_PLATE_SVG}'
            '<div class="e-title">No antibiotic disks detected</div>'
            '<div class="e-desc">The pipeline did not find paper disks in this image. '
            "Try a higher-contrast raw plate photograph with clearly visible disk halos.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return
    h1, h2, h3, h4 = st.columns([1, 2, 5, 2])
    h1.markdown('<div class="bs-th">Disk</div>', unsafe_allow_html=True)
    h2.markdown('<div class="bs-th">Zone</div>', unsafe_allow_html=True)
    h3.markdown('<div class="bs-th">Antibiotic</div>', unsafe_allow_html=True)
    h4.markdown('<div class="bs-th">Category</div>', unsafe_allow_html=True)
    st.markdown('<hr class="bs-hr" style="margin:2px 0 4px">', unsafe_allow_html=True)
    for i, zone in enumerate(result.zones):
        c1, c2, c3, c4 = st.columns([1, 2, 5, 2])
        c1.markdown(
            f'<div class="bs-td">{result.disks[i].label}</div>', unsafe_allow_html=True
        )
        c2.markdown(
            f'<div class="bs-td">{zone.diameter_mm:.1f} mm</div>', unsafe_allow_html=True
        )
        c3.selectbox(
            f"antibiotic_{i}",
            _ANTIBIOTIC_OPTIONS,
            key=_assignment_key(i),
            label_visibility="collapsed",
        )
        c4.markdown(
            f'<div class="bs-td-badge">{_category_badge(effective[i].category)}</div>',
            unsafe_allow_html=True,
        )


def _download_button(
    result: AnalysisResult, classifications: list[SusceptibilityResult]
) -> None:
    lines = (
        ["# BacterioScope Analysis Report", "",
         f"Calibration: {result.px_per_mm:.3f} px/mm",
         f"Plate diameter: {result.plate_diameter_px:.0f} px", "",
         "| Antibiotic | Zone (mm) | Category |",
         "|------------|-----------|----------|"]
        + [f"| {c.antibiotic} | {c.zone_diameter_mm:.1f} | {c.category} |"
           for c in classifications]
    )
    st.download_button(
        "Download report", "\n".join(lines), "bacterioscope_report.md", "text/markdown"
    )


def _show_results(result: AnalysisResult, classifier: CLSIClassifier) -> None:
    col_img, col_data = st.columns([10, 9], gap="large")
    is_hough = _is_hough_mode(result)
    effective = _effective_classifications(result, classifier)
    with col_img:
        st.markdown('<div class="bs-label">Annotated plate</div>', unsafe_allow_html=True)
        if result.annotated_image is not None:
            rgb = cv2.cvtColor(result.annotated_image, cv2.COLOR_BGR2RGB)
            st.image(rgb, use_container_width=True)
        st.markdown(
            f'<div class="bs-cap">{result.px_per_mm:.2f} px/mm &nbsp;·&nbsp; '
            f"{result.plate_diameter_px:.0f} px plate diameter</div>",
            unsafe_allow_html=True,
        )
    with col_data:
        st.markdown('<div class="bs-label">Classification</div>', unsafe_allow_html=True)
        _mode_indicator(is_hough)
        _metric_cards(effective)
        has_data = bool(result.zones)
        if has_data:
            st.markdown('<hr class="bs-hr">', unsafe_allow_html=True)
        if is_hough:
            _hough_table(result, effective)
        else:
            _results_table(result.classifications)
        if has_data:
            _download_button(result, effective)


def main() -> None:
    st.set_page_config(
        page_title="BacterioScope", layout="wide", initial_sidebar_state="expanded"
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="bs-header">'
        '<div class="bs-header-title">BacterioScope</div>'
        '<div class="bs-header-sub">'
        "Automated Kirby-Bauer antibiogram analysis — CLSI M100-Ed33 (2023) S/I/R classification"
        "</div></div>",
        unsafe_allow_html=True,
    )
    plate_mm, organism = _sidebar()
    pipeline = _build_pipeline(plate_mm, organism)
    uploaded = st.file_uploader(
        "plate", type=["jpg", "jpeg", "png", "bmp", "tiff"], label_visibility="collapsed"
    )
    st.markdown(
        '<div class="bs-upload-hint">Upload a raw, unprocessed plate photograph '
        "(JPEG, PNG, TIFF). Pre-annotated images will produce overlapping annotations.</div>",
        unsafe_allow_html=True,
    )
    if uploaded is None:
        st.markdown(
            f'<div class="bs-welcome">{_PLATE_SVG}'
            '<div class="w-title">Upload a plate photograph to begin</div>'
            '<div class="w-desc">Use a raw image from the antibiogram plate — '
            "not already-annotated or previously processed.</div></div>",
            unsafe_allow_html=True,
        )
        return
    _sync_for_new_image(f"{uploaded.name}:{uploaded.size}")
    result = _run_pipeline(pipeline, uploaded)
    if result is None:
        return
    st.markdown('<div class="bs-panel">', unsafe_allow_html=True)
    _show_results(result, pipeline.classifier)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
