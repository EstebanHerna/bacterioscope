"""Run one complete synthetic plate -> BacterioScope report review locally.

Default invocation uses the public, generated ``plate_mixed_sir.png`` fixture,
assigns its known six-disk layout, optionally searches fixed INS/OPS alerts, and
calls the configured Nemotron model. The output is a research/demo artifact,
not a clinical result. Provider credentials are loaded from the repo .env and
are never printed.

Usage::

    python scripts/demo_agent_review.py
    python scripts/demo_agent_review.py --skip-alerts
    python scripts/demo_agent_review.py --image path/to/plate.png \
        --antibiotics ampicillin ciprofloxacin ceftriaxone meropenem gentamicin \
        trimethoprim-sulfamethoxazole
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

if TYPE_CHECKING:
    from bacterioscope.detection.detector import DiskResult

_DEFAULT_FIXTURE = REPO_ROOT / "examples" / "synthetic" / "plate_mixed_sir.png"
_DEFAULT_RULE_STANDARD = "CLSI M100-Ed36 2026"
_RULE_STANDARDS = ("CLSI M100-Ed33 2023", "CLSI M100-Ed36 2026")
_SIX_DISK_FIXTURE_LABELS = [
    "Meropenem",
    "Ciprofloxacin",
    "Ampicillin",
    "Ceftriaxone",
    "Imipenem",
    "Gentamicin",
]


def _assign_fixture_labels(
    *,
    image_path: Path,
    disks: list[DiskResult],
    center: tuple[int, int],
    supplied: list[str] | None,
) -> list[str]:
    from bacterioscope.panels.manager import PanelConfig, PanelManager

    if supplied is not None:
        if len(supplied) != len(disks):
            raise ValueError(
                f"--antibiotics has {len(supplied)} names but the pipeline detected "
                f"{len(disks)} disks"
            )
        clockwise_labels = supplied
    elif image_path.resolve() == _DEFAULT_FIXTURE.resolve() and len(disks) == 6:
        clockwise_labels = _SIX_DISK_FIXTURE_LABELS
    else:
        raise ValueError(
            "disk identity is manual in this project; for a custom image pass "
            "--antibiotics in clockwise order starting at 12 o'clock"
        )

    panel = PanelConfig(
        name="Manual synthetic/demo panel",
        organism_group="Enterobacteriaceae",
        standard="CLSI",
        antibiotics=clockwise_labels,
    )
    labels = PanelManager().assign(disks, panel, center)
    if labels is None:
        raise ValueError("disk count does not match the supplied panel")
    return labels


def main() -> int:
    configure_output = getattr(sys.stdout, "reconfigure", None)
    if callable(configure_output):
        configure_output(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--image", type=Path, default=_DEFAULT_FIXTURE)
    parser.add_argument(
        "--antibiotics",
        nargs="+",
        help="disk names clockwise from 12 o'clock (required for non-default images)",
    )
    parser.add_argument(
        "--organism", default="Escherichia coli", help="organism name for the rule tools"
    )
    parser.add_argument(
        "--rule-standard",
        choices=_RULE_STANDARDS,
        default=_DEFAULT_RULE_STANDARD,
        help=(
            "CLSI edition for expert-rule catalogs, independent of the "
            "measurement classifier (default: Ed36)"
        ),
    )
    parser.add_argument(
        "--skip-alerts", action="store_true", help="do not make the two Tavily searches"
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Missing dependency: install with `python -m pip install -e '.[agent]'`.")
        return 2

    load_dotenv(REPO_ROOT / ".env", override=False)

    from bacterioscope.agent.nemotron_client import TokenFactoryClient
    from bacterioscope.agent.orchestrator import review_plate
    from bacterioscope.integrations.tavily import TavilyAlertSearch
    from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig

    image_path = args.image if args.image.is_absolute() else (Path.cwd() / args.image)
    image_path = image_path.resolve()
    if not image_path.is_file():
        print(f"Image not found: {image_path}")
        return 2

    try:
        pipeline = BacterioScopePipeline(PipelineConfig(organism_group="Enterobacteriaceae"))
        analysis = pipeline.analyze(image_path)
        labels = _assign_fixture_labels(
            image_path=image_path,
            disks=analysis.disks,
            center=analysis.plate_center,
            supplied=args.antibiotics,
        )
        analysis = pipeline.reclassify_with_labels(analysis, labels)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Pipeline/assignment failed: {exc}")
        return 2

    print("BacterioScope full agent review — synthetic/demo use only")
    print(f"Image path: {image_path}")
    print(f"Image SHA-256: {analysis.image_sha256}")
    print(f"Detected disks: {len(analysis.disks)}")
    print(f"Classifier standard: {analysis.breakpoint_table_version}")
    print(f"Expert-rule catalog standard: {args.rule_standard}")
    print("Measurements:")
    for index, (classification, flags) in enumerate(
        zip(analysis.classifications, analysis.flags)
    ):
        flag_text = ",".join(flags) if flags else "none"
        print(
            f"  {index + 1}. {classification.antibiotic}: "
            f"{classification.zone_diameter_mm:.1f} mm; "
            f"{classification.category}; flags={flag_text}"
        )
        if "crop_boundary" in flags:
            print(
                "     REVIEW: the segmented shape nearly fills its own bounding "
                "box, suggesting it may follow the algorithm's search-window "
                "edge instead of the halo. This does not mean the photo itself "
                "is cropped. Verify the diameter manually."
            )

    client = TokenFactoryClient()
    if not client.configured:
        print("Warning: NEBIUS_API_KEY is missing; report will use deterministic fallback.")

    alert_sources = [] if args.skip_alerts else ["ins", "ops"]
    alert_search = TavilyAlertSearch(max_results=1, timeout_seconds=20)
    if alert_sources and not alert_search.configured:
        print("Warning: TAVILY_API_KEY is missing; alerts will be marked unavailable.")

    outcome = review_plate(
        analysis,
        organism=args.organism,
        rule_standard=args.rule_standard,
        client=client,
        alert_search=alert_search,
        alert_sources=alert_sources,
    )
    print(f"\nAgent report status: {outcome.status}")
    catalog_status = outcome.report.get("catalog_status", {})
    if isinstance(catalog_status, dict):
        print("Rule catalog status:")
        for name, status in catalog_status.items():
            print(f"  {name}: {status}")
        if catalog_status.get("intrinsic_resistance") == "rules_not_enabled_for_standard_or_review":
            print(
                "  Ed36 contains five intrinsic-resistance candidates, but they "
                "remain draft and are not executed."
            )
        if catalog_status.get("phenotype") == "no_rules_configured":
            print("  No AST phenotype-pattern rules are configured in this catalog.")
        if catalog_status.get("cascade") == "no_rules_configured":
            print("  No institution-specific cascade profile is configured.")
    if outcome.fallback_reason:
        print(f"Fallback reason: {outcome.fallback_reason}")
    print(json.dumps(outcome.report, ensure_ascii=False, indent=2))

    return 0 if outcome.status == "grounded_report" else 1


if __name__ == "__main__":
    raise SystemExit(main())
