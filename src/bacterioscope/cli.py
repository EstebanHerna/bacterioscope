"""Command-line interface for BacterioScope.

Run the pipeline from a terminal without writing any Python code.
Internally uses Typer to parse arguments and Rich to format the output table.

Available commands
------------------
``analyze``
    Run the full pipeline on a plate image file and print a colour-coded
    results table. Green = Susceptible, Yellow = Intermediate, Red = Resistant.
``version``
    Print the installed BacterioScope version string.

Usage examples
--------------
::

    # Basic analysis — prints table to the terminal
    python -m bacterioscope analyze plate.jpg

    # Save the annotated image alongside the printed table
    python -m bacterioscope analyze plate.jpg --output annotated.jpg

    # Override the default organism group and detection confidence
    python -m bacterioscope analyze plate.jpg \\
        --organism Enterobacteriaceae \\
        --confidence 0.4

    # Print version
    python -m bacterioscope version
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

if TYPE_CHECKING:
    from bacterioscope.pipeline import AnalysisResult

app = typer.Typer(help="BacterioScope: Automated AST from Kirby-Bauer images")
console = Console()


@app.command()
def analyze(
    image_path: Path = typer.Argument(..., help="Path to Kirby-Bauer plate image"),
    organism: str = typer.Option("Enterobacteriaceae", help="CLSI organism group"),
    output: Path | None = typer.Option(None, help="Save annotated image to path"),
    confidence: float = typer.Option(
        0.5, min=0.0, max=1.0, help="Detection confidence (0.0-1.0)"
    ),
    panel: str | None = typer.Option(
        None, help="Panel name for automatic antibiotic assignment by disk position"
    ),
    report: Path | None = typer.Option(
        None, help="Save an HTML analysis report to this path"
    ),
) -> None:
    """Analyze a Kirby-Bauer plate image and print an S/I/R results table.

    Runs the full BacterioScope pipeline in order:
    calibration -> disk detection -> zone segmentation -> CLSI classification.
    Prints a colour-coded table to the terminal.

    When --panel is provided, antibiotics are auto-assigned by angular disk
    position (clockwise from 12 o'clock) using the named panel YAML config.
    Disk count must match the panel exactly or auto-assignment is skipped.

    Args:
        image_path: Path to the plate photograph (JPEG, PNG, BMP, or TIFF).
        organism: CLSI organism group for breakpoint lookup.
        output: Optional path to save the annotated plate image.
        confidence: YOLOv8 detection confidence threshold (0.0-1.0).
        panel: Panel name (file stem from panels/ directory).
        report: Optional path to write an HTML analysis report.
    """
    import cv2

    from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig

    config = PipelineConfig(confidence_threshold=confidence, organism_group=organism)
    pl = BacterioScopePipeline(config)
    result = pl.analyze(image_path)

    if panel is not None:
        from bacterioscope.panels.manager import PanelManager
        pm = PanelManager()
        try:
            panel_cfg = pm.load(panel)
            labels = pm.assign(result.disks, panel_cfg, result.plate_center)
            if labels is None:
                console.print(
                    f"[yellow]Warning: {len(result.disks)} disks detected but panel "
                    f"'{panel}' has {len(panel_cfg.antibiotics)}. Skipping.[/yellow]"
                )
            else:
                result = pl.reclassify_with_labels(result, labels)
                console.print(f"Panel applied: {panel_cfg.name}")
        except FileNotFoundError as exc:
            console.print(f"[red]{exc}[/red]")

    _print_results_table(result)

    if output and result.annotated_image is not None:
        cv2.imwrite(str(output), result.annotated_image)
        console.print(f"Annotated image saved to: {output}")

    if report is not None:
        from bacterioscope.evaluation.plate_report import save_plate_report
        save_plate_report(result, report)
        console.print(f"Report saved to: {report}")


def _print_results_table(result: AnalysisResult) -> None:
    table = Table(title="BacterioScope Analysis Results")
    table.add_column("Antibiotic", style="cyan")
    table.add_column("Zone (mm)", justify="right")
    table.add_column("Category", justify="center")
    table.add_column("Flags")

    for i, cls in enumerate(result.classifications):
        style = {"S": "green", "I": "yellow", "R": "red"}.get(cls.category, "white")
        cat_cell = f"[{style}]{cls.category}[/{style}]"
        flags_text = ", ".join(result.flags[i]) if i < len(result.flags) else ""
        table.add_row(cls.antibiotic, f"{cls.zone_diameter_mm:.1f}", cat_cell, flags_text)

    console.print(table)
    console.print(
        f"\nCalibration: {result.px_per_mm:.2f} px/mm"
        f" (plate: {result.plate_diameter_px:.0f} px)"
    )


@app.command()
def version() -> None:
    """Print the installed BacterioScope package version."""
    console.print("BacterioScope v0.1.0")


if __name__ == "__main__":
    app()
