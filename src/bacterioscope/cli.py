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

import typer
from rich.console import Console
from rich.table import Table

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
) -> None:
    """Analyze a Kirby-Bauer plate image and print an S/I/R results table.

    Runs the full BacterioScope pipeline in order:
    calibration → disk detection → zone segmentation → CLSI classification.
    Prints a colour-coded table to the terminal.
    If --output is provided, saves the annotated image to that file path.

    Args:
        image_path: Path to the plate photograph (JPEG, PNG, BMP, or TIFF).
        organism: CLSI organism group for breakpoint lookup.
            Currently only 'Enterobacteriaceae' is supported.
        output: Optional file path to save the annotated plate image.
            If omitted, the annotated image is not saved.
        confidence: YOLOv8 detection confidence threshold (0.0–1.0).
            Detections with a score below this threshold are discarded.
            Has no effect in Hough fallback mode.
    """
    import cv2

    from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig

    config = PipelineConfig(
        confidence_threshold=confidence,
        organism_group=organism,
    )
    pipeline = BacterioScopePipeline(config)
    result = pipeline.analyze(image_path)

    table = Table(title="BacterioScope Analysis Results")
    table.add_column("Antibiotic", style="cyan")
    table.add_column("Zone (mm)", justify="right")
    table.add_column("Classification", justify="center")

    for cls in result.classifications:
        style = {"S": "green", "I": "yellow", "R": "red"}.get(cls.category, "white")
        classification = f"[{style}]{cls.category}[/{style}]"
        table.add_row(cls.antibiotic, f"{cls.zone_diameter_mm:.1f}", classification)

    console.print(table)
    console.print(
        f"\nCalibration: {result.px_per_mm:.2f} px/mm"
        f" (plate: {result.plate_diameter_px:.0f} px)"
    )

    if output and result.annotated_image is not None:
        cv2.imwrite(str(output), result.annotated_image)
        console.print(f"Annotated image saved to: {output}")


@app.command()
def version() -> None:
    """Print the installed BacterioScope package version."""
    console.print("BacterioScope v0.1.0")


if __name__ == "__main__":
    app()
