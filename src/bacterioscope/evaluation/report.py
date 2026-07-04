"""Evaluation report generation for BacterioScope pipeline assessment."""

from __future__ import annotations

from pathlib import Path
from typing import Any

_CSS = (
    "body{font-family:sans-serif;max-width:960px;margin:2em auto;padding:0 1em;color:#222}"
    "h1,h2{border-bottom:1px solid #ddd;padding-bottom:.3em}"
    "table{border-collapse:collapse;width:100%;margin-bottom:1.5em}"
    "th,td{border:1px solid #ccc;padding:.35em .7em;text-align:left}"
    "th{background:#f5f5f5}"
    "p{margin:.4em 0}"
)


def _pct(v: float) -> str:
    return f"{v:.1%}"


def _rate(rate: float, count: int) -> str:
    return f"{_pct(rate)} ({count})"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    sep = ["-" * max(len(h), 4) for h in headers]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _html_table(headers: list[str], rows: list[list[str]]) -> str:
    ths = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        body += f"<tr>{tds}</tr>"
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{body}</tbody></table>"


def _summary_rows(metrics: dict[str, Any]) -> list[list[str]]:
    rows = [
        ["Overall Accuracy", _pct(metrics["accuracy"])],
        ["Categorical Agreement (CA)", _pct(metrics["categorical_agreement"])],
    ]
    if "essential_agreement" in metrics:
        rows.append(["Essential Agreement (EA, +/-2 mm)", _pct(metrics["essential_agreement"])])
    if "zone_stats" in metrics:
        zs = metrics["zone_stats"]
        rows.append(["Zone Diameter MAE", f"{zs['mae_mm']:.2f} mm"])
        rows.append(["Pearson r", f"{zs['pearson_r']:.3f}"])
    return rows


def _error_rows(er: dict[str, Any]) -> list[list[str]]:
    return [
        ["Very Major Error (VME)", str(er["vme_count"]),
         _rate(er["vme_rate"], er["vme_count"]), "Predicted S, reference R"],
        ["Major Error (ME)", str(er["me_count"]),
         _rate(er["me_rate"], er["me_count"]), "Predicted R, reference S"],
        ["minor Error (mE)", str(er["minor_count"]),
         _rate(er["minor_rate"], er["minor_count"]), "Discordance involving I"],
    ]


def _per_class_rows(per_class: dict[str, Any]) -> list[list[str]]:
    rows = []
    for cat in ("S", "I", "R"):
        m = per_class[cat]
        rows.append([
            cat,
            _pct(m["precision"]),
            _pct(m["recall"]),
            _pct(m["f1"]),
            str(int(m["support"])),
        ])
    return rows


def _confusion_rows(cm: list[list[int]]) -> list[list[str]]:
    labels = ("S", "I", "R")
    return [
        [labels[i]] + [str(v) for v in row]
        for i, row in enumerate(cm)
    ]


def generate_markdown(metrics: dict[str, Any]) -> str:
    """Generate a Markdown evaluation report.

    Args:
        metrics: Dict produced by collect_metrics(). Required keys:
            accuracy, categorical_agreement, error_rates, per_class,
            confusion_matrix. Optional: essential_agreement, zone_stats.

    Returns:
        Markdown-formatted report string.
    """
    er = metrics["error_rates"]
    parts = [
        "# BacterioScope Evaluation Report\n",
        "## Summary\n",
        _md_table(["Metric", "Value"], _summary_rows(metrics)),
        "\n## Error Analysis\n",
        _md_table(
            ["Error Type", "Count", "Rate", "Definition"],
            _error_rows(er),
        ),
        f"\nVME denominator: {er['n_resistant']} resistant isolates.  ",
        f"ME denominator: {er['n_susceptible']} susceptible isolates.  ",
        f"mE denominator: {er['n_total']} total isolates.",
        "\n## Confusion Matrix\n",
        "Rows = reference class, columns = predicted class. Order: S, I, R.\n",
        _md_table(["Ref \\ Pred", "S", "I", "R"], _confusion_rows(metrics["confusion_matrix"])),
        "\n## Per-Class Metrics\n",
        _md_table(
            ["Class", "Precision", "Recall", "F1", "Support"],
            _per_class_rows(metrics["per_class"]),
        ),
    ]
    return "\n".join(parts)


def generate_html(metrics: dict[str, Any]) -> str:
    """Generate an HTML evaluation report.

    Args:
        metrics: Dict produced by collect_metrics().

    Returns:
        Standalone HTML string with inline CSS.
    """
    er = metrics["error_rates"]
    body_parts = [
        "<h1>BacterioScope Evaluation Report</h1>",
        "<h2>Summary</h2>",
        _html_table(["Metric", "Value"], _summary_rows(metrics)),
        "<h2>Error Analysis</h2>",
        _html_table(
            ["Error Type", "Count", "Rate", "Definition"],
            _error_rows(er),
        ),
        f"<p>VME denominator: {er['n_resistant']} resistant isolates.<br>",
        f"ME denominator: {er['n_susceptible']} susceptible isolates.<br>",
        f"mE denominator: {er['n_total']} total isolates.</p>",
        "<h2>Confusion Matrix</h2>",
        "<p>Rows = reference class, columns = predicted class. Order: S, I, R.</p>",
        _html_table(["Ref / Pred", "S", "I", "R"], _confusion_rows(metrics["confusion_matrix"])),
        "<h2>Per-Class Metrics</h2>",
        _html_table(
            ["Class", "Precision", "Recall", "F1", "Support"],
            _per_class_rows(metrics["per_class"]),
        ),
    ]
    body = "\n".join(body_parts)
    return (
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        "<meta charset='utf-8'>\n"
        "<title>BacterioScope Evaluation Report</title>\n"
        f"<style>{_CSS}</style>\n"
        f"</head>\n<body>\n{body}\n</body>\n</html>"
    )


def save_report(
    metrics: dict[str, Any],
    output_dir: Path,
    formats: list[str] | None = None,
) -> list[Path]:
    """Save evaluation report files to disk.

    Args:
        metrics: Dict produced by collect_metrics().
        output_dir: Directory to write report files into.
        formats: Output formats to generate. Supported: 'markdown', 'html'.
            Default is ['markdown'].

    Returns:
        List of paths to the written report files.

    Raises:
        ValueError: If an unsupported format is requested.
    """
    if formats is None:
        formats = ["markdown"]
    supported = {"markdown", "html"}
    unknown = set(formats) - supported
    if unknown:
        raise ValueError(f"Unsupported report format(s): {unknown}")

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if "markdown" in formats:
        path = output_dir / "evaluation_report.md"
        path.write_text(generate_markdown(metrics), encoding="utf-8")
        written.append(path)

    if "html" in formats:
        path = output_dir / "evaluation_report.html"
        path.write_text(generate_html(metrics), encoding="utf-8")
        written.append(path)

    return written
