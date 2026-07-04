"""Streamlit interactive demo for BacterioScope.

Run with:
    streamlit run src/bacterioscope/app.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import streamlit as st

from bacterioscope.classification.clsi import SusceptibilityResult
from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline, PipelineConfig

_CATEGORY_LABEL: dict[str, str] = {
    "S": "Susceptible",
    "I": "Intermediate",
    "R": "Resistant",
}

_CSS = """
<style>
@keyframes bs-fadein {
  from { opacity: 0; transform: translateY(5px); }
  to   { opacity: 1; transform: translateY(0);   }
}

.bs-panel {
  animation: bs-fadein 220ms cubic-bezier(0.23, 1, 0.32, 1) both;
}

.bs-banner {
  background: rgba(30, 50, 90, 0.55);
  border: 1px solid rgba(74, 127, 212, 0.3);
  border-left: 3px solid #4a7fd4;
  border-radius: 6px;
  padding: 11px 15px;
  margin-bottom: 14px;
  font-size: 0.84rem;
  line-height: 1.6;
  color: #a8bcd8;
  animation: bs-fadein 200ms cubic-bezier(0.23, 1, 0.32, 1) both;
}
.bs-banner strong { color: #c8d8f0; font-weight: 600; }
.bs-banner--ok {
  background: rgba(20, 60, 35, 0.5);
  border-color: rgba(74, 180, 110, 0.3);
  border-left-color: #4ab46e;
  color: #96d8b0;
}
.bs-banner--ok strong { color: #b6ecd0; }

.bs-metrics {
  display: flex;
  gap: 8px;
  margin: 12px 0;
}
.bs-metric {
  flex: 1;
  padding: 14px 10px 12px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid rgba(255,255,255,0.07);
}
.bs-metric .m-value {
  font-size: 1.9rem;
  font-weight: 700;
  line-height: 1.1;
}
.bs-metric .m-label {
  font-size: 0.7rem;
  margin-top: 3px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  opacity: 0.75;
}
.bs-metric--s { background: rgba(26, 61, 43, 0.85); }
.bs-metric--s .m-value, .bs-metric--s .m-label { color: #86efac; }
.bs-metric--i { background: rgba(61, 48, 16, 0.85); }
.bs-metric--i .m-value, .bs-metric--i .m-label { color: #fde68a; }
.bs-metric--r { background: rgba(61, 16, 16, 0.85); }
.bs-metric--r .m-value, .bs-metric--r .m-label { color: #fca5a5; }

.bs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  margin-top: 8px;
}
.bs-table th {
  text-align: left;
  padding: 7px 12px;
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: #6e7b94;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.bs-table td {
  padding: 9px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  vertical-align: middle;
}
.bs-table tbody tr {
  opacity: 0;
  animation: bs-fadein 190ms cubic-bezier(0.23, 1, 0.32, 1) forwards;
}
.bs-table tbody tr:nth-child(1) { animation-delay: 50ms; }
.bs-table tbody tr:nth-child(2) { animation-delay: 90ms; }
.bs-table tbody tr:nth-child(3) { animation-delay: 130ms; }
.bs-table tbody tr:nth-child(4) { animation-delay: 170ms; }
.bs-table tbody tr:nth-child(5) { animation-delay: 210ms; }
.bs-table tbody tr:nth-child(6) { animation-delay: 250ms; }
.bs-table tbody tr:nth-child(7) { animation-delay: 290ms; }
.bs-table tbody tr:nth-child(8) { animation-delay: 330ms; }

.bs-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 4px;
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.bs-badge--s { background: rgba(26,61,43,0.9); color: #86efac; }
.bs-badge--i { background: rgba(61,48,16,0.9);  color: #fde68a; }
.bs-badge--r { background: rgba(61,16,16,0.9);  color: #fca5a5; }
.bs-badge--unknown { background: rgba(50,50,55,0.7); color: #9098a8; }

.bs-empty {
  text-align: center;
  padding: 44px 20px;
  color: #6e7b94;
}
.bs-empty h3 {
  font-size: 1rem;
  font-weight: 600;
  color: #b0bcd0;
  margin-bottom: 6px;
}
.bs-empty p {
  font-size: 0.84rem;
  line-height: 1.65;
  max-width: 360px;
  margin: 0 auto;
}

@media (prefers-reduced-motion: reduce) {
  .bs-panel, .bs-banner,
  .bs-table tbody tr { animation: none; opacity: 1; }
}
</style>
"""


@st.cache_resource
def _build_pipeline(plate_mm: float, organism: str) -> BacterioScopePipeline:
    return BacterioScopePipeline(
        PipelineConfig(plate_diameter_mm=plate_mm, organism_group=organism)
    )


def _sidebar() -> tuple[float, str]:
    st.sidebar.header("Configuration")
    plate_mm = st.sidebar.number_input(
        "Plate diameter (mm)", min_value=50.0, max_value=150.0, value=90.0, step=1.0
    )
    organism = st.sidebar.selectbox(
        "Organism group", options=["Enterobacteriaceae"], index=0
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("CLSI M100-Ed33 (2023)  \nISO 20776-2")
    return float(plate_mm), str(organism)


def _is_hough_mode(result: AnalysisResult) -> bool:
    if not result.classifications:
        return True
    return any(c.antibiotic.startswith("disk_") for c in result.classifications)


def _detection_banner(is_hough: bool) -> None:
    if is_hough:
        st.markdown(
            '<div class="bs-banner">'
            "<strong>Geometric detection mode (Hough circles).</strong> "
            "Antibiotic identification requires the trained YOLOv8 model (Phase 1). "
            "Zone diameters are measured; S/I/R classification is pending disk labeling."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="bs-banner bs-banner--ok">'
            "<strong>YOLOv8 model active.</strong> "
            "Disk identification and zone measurement are fully automated."
            "</div>",
            unsafe_allow_html=True,
        )


def _category_badge(category: str) -> str:
    cat_cls = category.lower() if category in ("S", "I", "R") else "unknown"
    return f'<span class="bs-badge bs-badge--{cat_cls}">{category}</span>'


def _metric_cards(classifications: list[SusceptibilityResult]) -> None:
    counts = {k: sum(1 for c in classifications if c.category == k) for k in ("S", "I", "R")}
    cards = "".join(
        f'<div class="bs-metric bs-metric--{cat.lower()}">'
        f'<div class="m-value">{counts[cat]}</div>'
        f'<div class="m-label">{_CATEGORY_LABEL[cat]}</div>'
        "</div>"
        for cat in ("S", "I", "R")
    )
    st.markdown(f'<div class="bs-metrics">{cards}</div>', unsafe_allow_html=True)


def _results_table(classifications: list[SusceptibilityResult]) -> None:
    if not classifications:
        st.markdown(
            '<div class="bs-empty">'
            "<h3>No disks detected</h3>"
            "<p>The pipeline did not find antibiotic disks in this image. "
            "Try a higher-contrast raw plate photograph with clearly visible paper disks.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return
    rows = "".join(
        f"<tr>"
        f"<td>{cls.antibiotic}</td>"
        f'<td style="font-variant-numeric:tabular-nums">{cls.zone_diameter_mm:.1f}</td>'
        f"<td>{_category_badge(cls.category)}</td>"
        f"</tr>"
        for cls in classifications
    )
    st.markdown(
        '<table class="bs-table"><thead><tr>'
        "<th>Antibiotic</th><th>Zone (mm)</th><th>Category</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )


def _download_button(result: AnalysisResult) -> None:
    lines = [
        "# BacterioScope Analysis Report",
        "",
        f"Calibration: {result.px_per_mm:.3f} px/mm",
        f"Plate diameter: {result.plate_diameter_px:.0f} px",
        "",
        "| Antibiotic | Zone (mm) | Category |",
        "|------------|-----------|----------|",
    ] + [
        f"| {cls.antibiotic} | {cls.zone_diameter_mm:.1f} | {cls.category} |"
        for cls in result.classifications
    ]
    st.download_button(
        label="Download report",
        data="\n".join(lines),
        file_name="bacterioscope_report.md",
        mime="text/markdown",
    )


def _show_results(result: AnalysisResult) -> None:
    col_img, col_data = st.columns([1, 1], gap="large")
    with col_img:
        st.subheader("Annotated plate")
        if result.annotated_image is not None:
            rgb = cv2.cvtColor(result.annotated_image, cv2.COLOR_BGR2RGB)
            st.image(rgb, use_container_width=True)
        st.caption(
            f"Calibration: {result.px_per_mm:.2f} px/mm"
            f"  |  Plate: {result.plate_diameter_px:.0f} px"
        )
    with col_data:
        st.subheader("Classification")
        _detection_banner(_is_hough_mode(result))
        _metric_cards(result.classifications)
        _results_table(result.classifications)
        if result.classifications:
            _download_button(result)


def main() -> None:
    st.set_page_config(
        page_title="BacterioScope",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    st.title("BacterioScope")
    st.caption(
        "Automated Kirby-Bauer antibiogram analysis — "
        "CLSI M100-Ed33 (2023) S/I/R classification."
    )
    plate_mm, organism = _sidebar()
    pipeline = _build_pipeline(plate_mm, organism)
    uploaded = st.file_uploader(
        "Upload plate image (JPEG, PNG, BMP, TIFF)",
        type=["jpg", "jpeg", "png", "bmp", "tiff"],
    )
    st.caption(
        "Upload a raw, unprocessed plate photograph. "
        "Pre-annotated images will produce overlapping annotations."
    )
    if uploaded is None:
        st.markdown(
            '<div class="bs-empty">'
            "<h3>Upload a plate photograph to begin</h3>"
            "<p>Use a raw image taken directly from the antibiogram plate — "
            "not an already-annotated or previously processed image.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return
    with tempfile.NamedTemporaryFile(
        suffix=Path(uploaded.name).suffix.lower() or ".png", delete=False
    ) as tmp:
        tmp.write(uploaded.read())
        tmp_path = Path(tmp.name)
    try:
        with st.spinner("Analyzing..."):
            result = pipeline.analyze(tmp_path)
    except (ValueError, FileNotFoundError) as exc:
        st.error(f"Analysis failed: {exc}")
        return
    finally:
        tmp_path.unlink(missing_ok=True)
    st.markdown('<div class="bs-panel">', unsafe_allow_html=True)
    _show_results(result)
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
