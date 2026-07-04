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
    confidence: float = typer.Option(0.5, min=0.0, max=1.0, help="Detection confidence (0.0-1.0)"),
) -> None:
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
    console.print("BacterioScope v0.1.0")


if __name__ == "__main__":
    app()
