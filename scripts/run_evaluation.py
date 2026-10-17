"""Run the BacterioScope evaluation and write results plus a Markdown report.

Stage 1 (always, no network): the vision pipeline against the eight
synthetic plates' drawn geometry -- detection, mm error, measurement-induced
category agreement. Stage 2 (``--live``): the real agent through Nebius Token
Factory on the same plates, once routed and once forced to Ultra.

Usage::

    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --live --alerts ins ops
    python scripts/run_evaluation.py --live --prices prices.json

``prices.json`` maps exact model IDs to ``[usd_per_M_input, usd_per_M_output]``
copied from your own Token Factory console; without it, cost is not reported.
Credentials come from the environment (or a local ``.env``) and are never
printed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from bacterioscope.evaluation.synthetic_benchmark import (  # noqa: E402
    evaluate_plate,
    load_synthetic_truth,
    summarize,
)
from bacterioscope.pipeline import BacterioScopePipeline, PipelineConfig  # noqa: E402

_SYNTHETIC_DIR = REPO_ROOT / "examples" / "synthetic"
_ORGANISM = "Escherichia coli"
_SECRET_VARS = ("NEBIUS_API_KEY", "TAVILY_API_KEY")


def _redact(message: str) -> str:
    for name in _SECRET_VARS:
        secret = os.getenv(name, "")
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[:300]


def _commit() -> str:
    try:
        return subprocess.run(  # nosec B603 B607
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _deterministic_stage(truth_path: Path) -> tuple[dict[str, Any], list[tuple[str, Any]]]:
    pipeline = BacterioScopePipeline(PipelineConfig())
    outcomes, labeled = [], []
    for plate in load_synthetic_truth(truth_path):
        result = pipeline.analyze(_SYNTHETIC_DIR / plate.image)
        outcome = evaluate_plate(plate, result, pipeline.classifier)
        outcomes.append(outcome)
        labeled.append((plate.image, pipeline.reclassify_with_labels(result, list(outcome.labels))))
        print(f"  {plate.image}: {sum(d.detected for d in outcome.disks)}/{outcome.n_true} matched")
    return summarize(outcomes), labeled


def _fetch_alerts(sources: list[str]) -> tuple[list[Any], dict[str, str]]:
    from bacterioscope.integrations.tavily import (
        TavilyAlertSearch,
        TavilyConfigurationError,
        TavilySearchError,
    )

    alerts: list[Any] = []
    status: dict[str, str] = {}
    searcher = TavilyAlertSearch()
    for source in sources:
        try:
            found = searcher.search_amr_alerts(source)
        except (TavilyConfigurationError, TavilySearchError) as exc:
            status[source] = f"unavailable ({_redact(type(exc).__name__)})"
            continue
        alerts.extend(found)
        status[source] = f"{len(found)} alerts"
    return alerts, status


def _live_stage(
    labeled: list[tuple[str, Any]], args: argparse.Namespace
) -> dict[str, Any]:
    from bacterioscope.agent.nemotron_client import TokenFactoryClient
    from bacterioscope.agent.orchestrator import review_plate
    from bacterioscope.evaluation.agent_benchmark import (
        TIERS,
        resolve_tier_models,
        run_agent_benchmark,
        summarize_agent_runs,
    )

    catalog = TokenFactoryClient(models={}).list_models()
    overrides = {tier: os.getenv(f"NEBIUS_MODEL_{tier.upper()}", "") for tier in TIERS}
    models = resolve_tier_models(catalog, overrides)
    print(f"  models: {models}")
    client = TokenFactoryClient(models=models)
    alerts, alert_status = _fetch_alerts(args.alerts) if args.alerts else ([], {})
    records = run_agent_benchmark(
        labeled, client=client, review=review_plate, organism=_ORGANISM,
        modes=args.modes, public_alerts=alerts,
    )
    prices = None
    if args.prices:
        raw = json.loads(Path(args.prices).read_text(encoding="utf-8"))
        prices = {model: (float(v[0]), float(v[1])) for model, v in raw.items()}
    return {
        "models": models,
        "nemotron_catalog": [m for m in catalog if "nemotron" in m.lower()],
        "alerts": alert_status,
        "summary": summarize_agent_runs(records, prices),
        "runs": [
            {
                "image": r.image, "mode": r.mode, "status": r.status,
                "fallback_reason": r.fallback_reason, "latency_ms": round(r.latency_ms, 1),
                "prompt_tokens": r.tokens[0], "completion_tokens": r.tokens[1],
                "tiers": [c.used_tier for c in r.calls], "cited_evidence": r.cited_evidence,
            }
            for r in records
        ],
        "priced": prices is not None,
    }


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def _num(value: float | None, unit: str = "") -> str:
    return "n/a" if value is None else f"{value:.2f}{unit}"


def _render_report(results: dict[str, Any]) -> str:
    det = results["deterministic"]
    m, c, d = det["measurement"], det["categorical"], det["detection"]
    lines = [
        "# BacterioScope evaluation report",
        "",
        f"Generated {results['generated_at']} from commit `{results['commit']}` by "
        "`scripts/run_evaluation.py`. Synthetic plates only for stage 1; see "
        "`docs/VALIDATION_REPORT.md` for real-photo measurement (much worse).",
        "",
        "## Stage 1 -- vision pipeline vs drawn geometry (8 synthetic plates)",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Disk recall (matched / drawn) | {_pct(d['recall'])} "
        f"({d['matched']}/{d['true_disks']}) |",
        f"| Disk precision (matched / detections) | {_pct(d['precision'])} |",
        f"| Plates with exact disk count | {d['plates_with_exact_count']}/{det['n_plates']} |",
        f"| EA ±2 mm, drawn frame | {_pct(m['drawn_frame']['ea'])} |",
        f"| MAE / bias, drawn frame | {_num(m['drawn_frame']['mae_mm'], ' mm')} / "
        f"{_num(m['drawn_frame']['bias_mm'], ' mm')} |",
        f"| EA ±2 mm, nominal scenario values | {_pct(m['nominal_frame']['ea'])} |",
        f"| EA, unflagged vs flagged disks | {_pct(m['unflagged']['ea'])} vs "
        f"{_pct(m['flagged']['ea'])} (flagged {_pct(m['flagged_fraction'])}) |",
        f"| Measurement-induced CA | {_pct(c['ca'])} (n={c['n']}) |",
        f"| Very major / major / minor | {c['very_major']} / {c['major']} / {c['minor']} |",
        f"| Very major + major on **unflagged** disks | "
        f"{det['categorical_unflagged']['very_major'] + det['categorical_unflagged']['major']}"
        f" of {det['categorical_unflagged']['n']} |",
        f"| Very major + major on flagged disks | "
        f"{det['categorical_flagged']['very_major'] + det['categorical_flagged']['major']}"
        f" of {det['categorical_flagged']['n']} |",
        "",
        "The drawn frame is the reference: the generator draws the plate rim with a "
        "252 px radius, which the pipeline calibrates as 90 mm, while the scenario "
        "table's nominal values assume a different scale and run ~6% larger. Categories "
        "on both sides come from the same CLSI Ed33 classifier, so they isolate "
        "measurement error; SDD is treated like I.",
        "",
    ]
    live = results.get("live")
    if live is None:
        lines += ["## Stage 2 -- live agent", "", "Not run (no `--live`).", ""]
        return "\n".join(lines)
    lines += [
        "## Stage 2 -- live agent on Nebius Token Factory",
        "",
        f"Models resolved from the live catalog: `{live['models']}`. "
        f"Alerts: {live['alerts'] or 'not requested'}.",
        "",
        "| Mode | Grounded | p50 / p95 latency | Prompt / completion tokens | Tier mix "
        "| Cost per plate |",
        "|---|---|---|---|---|---|",
    ]
    for mode, s in live["summary"].items():
        cost = (
            "not priced" if s["cost_usd_per_plate"] is None
            else f"${s['cost_usd_per_plate']:.5f}"
        )
        lines.append(
            f"| {mode} | {s['grounded']}/{s['plates']} ({_pct(s['grounded_rate'])}) | "
            f"{_num(s['latency_ms_p50'], ' ms')} / {_num(s['latency_ms_p95'], ' ms')} | "
            f"{s['prompt_tokens']} / {s['completion_tokens']} | {s['tier_mix']} | {cost} |"
        )
    lines += ["", "Fallback reasons per mode: " + json.dumps(
        {mode: s["fallback_reasons"] for mode, s in live["summary"].items()}
    ), ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--truth", type=Path, default=_SYNTHETIC_DIR / "ground_truth.json")
    parser.add_argument(
        "--output-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "evaluation"
    )
    parser.add_argument("--live", action="store_true", help="Also run the live agent (billable).")
    parser.add_argument("--modes", nargs="+", default=["routed", "ultra_only"])
    parser.add_argument("--alerts", nargs="*", default=[], choices=["ins", "ops"])
    parser.add_argument("--prices", type=str, default=None)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass

    print("Stage 1: deterministic synthetic benchmark")
    deterministic, labeled = _deterministic_stage(args.truth)
    results: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "commit": _commit(),
        "deterministic": deterministic,
    }
    if args.live:
        print("Stage 2: live agent")
        try:
            results["live"] = _live_stage(labeled, args)
        except Exception as exc:  # noqa: BLE001 -- report any live failure without secrets
            print(f"  live stage failed: {_redact(f'{type(exc).__name__}: {exc}')}")
            results["live_error"] = _redact(f"{type(exc).__name__}: {exc}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation_results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "EVALUATION_REPORT.md").write_text(_render_report(results), encoding="utf-8")
    print(f"Wrote {args.output_dir}")
    return 1 if args.live and "live_error" in results else 0


if __name__ == "__main__":
    sys.exit(main())
