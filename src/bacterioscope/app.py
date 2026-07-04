"""Streamlit interactive demo for BacterioScope.

Run with:
    streamlit run src/bacterioscope/app.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import cv2
import streamlit as st

from bacterioscope.pipeline import AnalysisResult, BacterioScopePipeline, PipelineConfig

st.set_page_config(
    page_title="BacterioScope",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CATEGORY_COLORS = {"S": "#d4edda", "I": "#fff3cd", "R": "#f8d7da"}


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
    organism = st.sidebar.selectbox("Organism group", options=["Enterobacteriaceae"], index=0)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**References**  \nCLSI M100-Ed33 (2023)  \nISO 20776-2")
    return float(plate_mm), str(organism)


def _show_results(result: AnalysisResult) -> None:
    col_img, col_tbl = st.columns([1, 1], gap="large")

    with col_img:
        st.subheader("Annotated plate")
        if result.annotated_image is not None:
            rgb = cv2.cvtColor(result.annotated_image, cv2.COLOR_BGR2RGB)
            st.image(rgb, use_container_width=True)
        st.caption(
            f"Calibration: {result.px_per_mm:.2f} px/mm  |  "
            f"Plate: {result.plate_diameter_px:.0f} px diameter"
        )

    with col_tbl:
        st.subheader("Results")
        cls_list = result.classifications
        if not cls_list:
            st.info("No antibiotic disks detected.")
        else:
            for cls in cls_list:
                bg = _CATEGORY_COLORS.get(cls.category, "#f8f9fa")
                st.markdown(
                    f'<div style="background:{bg};padding:8px 12px;margin:4px 0;'
                    f'border-radius:6px;font-family:monospace">'
                    f'<strong>{cls.antibiotic}</strong> — '
                    f'{cls.zone_diameter_mm:.1f} mm — '
                    f'<strong>{cls.category}</strong></div>',
                    unsafe_allow_html=True,
                )
            counts = {k: sum(1 for c in cls_list if c.category == k) for k in ("S", "I", "R")}
            c1, c2, c3 = st.columns(3)
            c1.metric("Susceptible", counts["S"])
            c2.metric("Intermediate", counts["I"])
            c3.metric("Resistant", counts["R"])
            _download_button(result)


def _download_button(result: AnalysisResult) -> None:
    lines = [
        "# BacterioScope Analysis Report",
        "",
        f"**Calibration:** {result.px_per_mm:.3f} px/mm",
        f"**Plate diameter:** {result.plate_diameter_px:.0f} px",
        "",
        "| Antibiotic | Zone (mm) | Category |",
        "|------------|-----------|----------|",
    ]
    for cls in result.classifications:
        lines.append(f"| {cls.antibiotic} | {cls.zone_diameter_mm:.1f} | {cls.category} |")
    md = "\n".join(lines)
    st.download_button(
        label="Download report (Markdown)",
        data=md,
        file_name="bacterioscope_report.md",
        mime="text/markdown",
    )


def main() -> None:
    st.title("BacterioScope")
    st.caption(
        "Automated Kirby-Bauer antibiogram analysis — "
        "CLSI 2023 S/I/R classification from a plate photograph."
    )

    plate_mm, organism = _sidebar()
    pipeline = _build_pipeline(plate_mm, organism)

    uploaded = st.file_uploader(
        "Upload plate image (JPEG, PNG, BMP, TIFF)",
        type=["jpg", "jpeg", "png", "bmp", "tiff"],
    )

    if uploaded is None:
        st.markdown(
            "Upload a photograph of a Kirby-Bauer plate to run the analysis.  \n"
            "The pipeline detects antibiotic disks, segments inhibition zones, "
            "measures diameters, and classifies each disk as S / I / R per CLSI 2023."
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

    _show_results(result)


if __name__ == "__main__":
    main()
