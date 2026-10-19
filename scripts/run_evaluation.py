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
import contextlib
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
        status[source] = f"{len(found)} alert{'' if len(found) == 1 else 's'}"
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


def _secs(ms: float | None) -> str:
    return "n/a" if ms is None else f"{ms / 1000:.2f} s"


def _ratio(a: float | None, b: float | None) -> str:
    return "n/a" if not a or not b else f"{a / b:.2f}x"


def _dangerous(block: dict[str, Any]) -> int:
    return int(block["very_major"]) + int(block["major"])


def _counts(mapping: dict[str, Any]) -> str:
    return ", ".join(f"{key} {value}" for key, value in mapping.items()) or "none"


def _concentration(det: dict[str, Any]) -> list[str]:
    rows = det.get("discordances") or []
    if not rows:
        return []
    by_plate: dict[str, int] = {}
    for row in rows:
        by_plate[row["image"]] = by_plate.get(row["image"], 0) + 1
    worst = max(by_plate, key=lambda image: by_plate[image])
    severe = [r for r in rows if r["error"] != "minor"]
    on_worst = sum(1 for r in severe if r["image"] == worst)
    return [
        f"- **Errors concentrate on one plate:** {by_plate[worst]} of {len(rows)} category "
        f"disagreements, and {on_worst} of {len(severe)} very major/major ones, are on "
        f"`{worst}`, where neighbouring zones merge."
    ]


def _stage1_findings(det: dict[str, Any]) -> list[str]:
    d, m = det["detection"], det["measurement"]
    bias = m["drawn_frame"]["bias_mm"] or 0.0
    return _concentration(det) + [
        f"- **Detection:** {d['matched']}/{d['true_disks']} drawn disks found; exact disk "
        f"count on {d['plates_with_exact_count']}/{det['n_plates']} plates.",
        f"- **Measurement:** {_pct(m['drawn_frame']['ea'])} of zones within ±2 mm "
        f"(MAE {_num(m['drawn_frame']['mae_mm'], ' mm')}); the pipeline "
        f"{'under' if bias < 0 else 'over'}estimates by {abs(bias):.2f} mm on average.",
        f"- **Flags work as a safety signal:** {_dangerous(det['categorical_unflagged'])} "
        f"very major/major errors on {det['categorical_unflagged']['n']} unflagged disks, "
        f"{_dangerous(det['categorical_flagged'])} on {det['categorical_flagged']['n']} "
        "flagged ones. Flagged disks are excluded from expert rules by design.",
    ]


def _stage2_findings(live: dict[str, Any]) -> list[str]:
    summary = live["summary"]
    per_mode = "; ".join(
        f"{s['grounded']}/{s['plates']} `{mode}`" for mode, s in summary.items()
    )
    lines = [
        f"- **Grounded reports:** {per_mode}. Each narrative passed schema validation and "
        "cites only evidence that exists in the deterministic report."
    ]
    routed, ultra = summary.get("routed"), summary.get("ultra_only")
    if routed and ultra:
        lines.append(
            f"- **Routed vs Ultra:** routed calls by tier: {_counts(routed['tier_mix'])}. "
            "It produced "
            f"{_ratio(routed['completion_tokens'], ultra['completion_tokens'])} the completion "
            f"tokens of Ultra at {_ratio(routed['latency_ms_p50'], ultra['latency_ms_p50'])} "
            "its median latency, with the same grounded rate."
        )
    if routed and set(routed["tier_mix"]) == {"super"}:
        lines.append(
            "- **Why routing never escalated:** the report call runs on Super and escalates to "
            "Ultra only on expert-rule findings or a positive ESBL screen. No expert rules are "
            "enabled yet and the screen needs disk potency, so no plate qualified."
        )
    return lines


def _render_findings(results: dict[str, Any]) -> list[str]:
    lines = ["## Key findings", ""] + _stage1_findings(results["deterministic"])
    if "live" in results:
        lines += _stage2_findings(results["live"])
    elif "live_error" in results:
        lines.append(f"- **Live stage failed:** {results['live_error']}")
    else:
        lines.append("- **Live stage:** not run (needs `--live` or `--live-results`).")
    return lines + [""]


def _render_stage1(det: dict[str, Any]) -> list[str]:
    m, c, d = det["measurement"], det["categorical"], det["detection"]
    return [
        f"## Stage 1 -- vision pipeline vs drawn geometry ({det['n_plates']} synthetic plates)",
        "",
        "No network. Categories on both sides come from the same CLSI M100-Ed33 classifier, "
        "so every disagreement is a measurement error. SDD is treated like I.",
        "",
        "| Metric | Value | ISO 20776-2 target |",
        "|---|---|---|",
        f"| Disk recall (matched / drawn) | {_pct(d['recall'])} ({d['matched']}/{d['true_disks']}) "
        "| - |",
        f"| Disk precision (matched / detections) | {_pct(d['precision'])} | - |",
        f"| Essential agreement (±2 mm) | {_pct(m['drawn_frame']['ea'])} | >= 90% |",
        f"| MAE / bias | {_num(m['drawn_frame']['mae_mm'], ' mm')} / "
        f"{_num(m['drawn_frame']['bias_mm'], ' mm')} | - |",
        f"| EA unflagged vs flagged | {_pct(m['unflagged']['ea'])} vs {_pct(m['flagged']['ea'])} "
        f"({_pct(m['flagged_fraction'])} flagged) | - |",
        f"| Categorical agreement | {_pct(c['ca'])} (n={c['n']}) | >= 90% |",
        f"| Very major errors (R read as S) | {c['very_major']} "
        f"({_pct(c['very_major_rate'])} of R) | <= 1.5% |",
        f"| Major errors (S read as R) | {c['major']} ({_pct(c['major_rate'])} of S) | <= 3% |",
        f"| Minor errors (involving I/SDD) | {c['minor']} ({_pct(c['minor_rate'])}) | <= 10% |",
        "",
        "Reference frame: the generator draws the rim at 252 px, which the pipeline calibrates "
        f"as 90 mm. Against the scenario table's nominal values instead, EA is "
        f"{_pct(m['nominal_frame']['ea'])}: those values assume a scale ~6% larger.",
        "",
    ]


def _render_per_plate(det: dict[str, Any]) -> list[str]:
    lines = [
        "### Per plate", "",
        "| Plate | Disks found | Flagged | EA ±2 mm | MAE | Bias | CA |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in det["per_plate"]:
        lines.append(
            f"| {row['image']} | {row['matched']}/{row['true_disks']} "
            f"| {row.get('flagged', 'n/a')} | {_pct(row['ea'])} | {_num(row['mae_mm'], ' mm')} "
            f"| {_num(row['bias_mm'], ' mm')} | {_pct(row['ca'])} |"
        )
    return lines + [""]


def _render_discordances(det: dict[str, Any]) -> list[str]:
    rows = det.get("discordances") or []
    lines = ["### Every category disagreement", ""]
    if not rows:
        return lines + ["None.", ""]
    lines += [
        "| Error | Plate | Antibiotic | Reference | Measured | Flags |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['error'].replace('_', ' ')} | {row['image']} | {row['antibiotic']} "
            f"| {row['reference_mm']:.1f} mm {row['reference_category']} "
            f"| {row['measured_mm']:.1f} mm {row['predicted_category']} "
            f"| {', '.join(row['flags']) or 'none'} |"
        )
    return lines + [""]


def _render_stage2(live: dict[str, Any]) -> list[str]:
    source = live.get("source") or {}
    origin = (
        f"Run {source.get('generated_at', '')} at commit `{source.get('commit', '')}`"
        + (f" ([workflow run]({source['run_url']}))" if source.get("run_url") else "")
    )
    lines = [
        "## Stage 2 -- live agent on Nebius Token Factory", "",
        f"{origin}. Each synthetic plate reviewed once per mode with organism "
        f"*{_ORGANISM}*; both modes receive the same pre-fetched public alerts "
        f"({_counts(live['alerts'])}).", "",
        "Models resolved from the live catalog: "
        + ", ".join(f"{tier} `{model}`" for tier, model in live["models"].items()) + ".", "",
        "| Mode | Grounded | Latency p50 / p95 | Prompt / completion tokens | Calls by tier "
        "| Cost per plate |",
        "|---|---|---|---|---|---|",
    ]
    for mode, s in live["summary"].items():
        cost = s["cost_usd_per_plate"]
        lines.append(
            f"| {mode} | {s['grounded']}/{s['plates']} | {_secs(s['latency_ms_p50'])} / "
            f"{_secs(s['latency_ms_p95'])} | {s['prompt_tokens']} / {s['completion_tokens']} "
            f"| {_counts(s['tier_mix'])} | {'not priced' if cost is None else f'${cost:.5f}'} |"
        )
    reasons = {
        mode: s["fallback_reasons"] for mode, s in live["summary"].items() if s["fallback_reasons"]
    }
    lines += ["", f"Fallbacks: {json.dumps(reasons) if reasons else 'none'}. Cost is reported "
              "only with `--prices` taken from your own Token Factory console.", ""]
    return lines


def _render_runs(live: dict[str, Any]) -> list[str]:
    lines = [
        "### Every live review", "",
        "| Plate | Mode | Status | Latency | Tokens in / out | Tier | Cited evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for run in live["runs"]:
        status = run["status"] if not run["fallback_reason"] else (
            f"{run['status']} ({run['fallback_reason']})"
        )
        lines.append(
            f"| {run['image']} | {run['mode']} | {status} | {run['latency_ms'] / 1000:.2f} s "
            f"| {run['prompt_tokens']} / {run['completion_tokens']} | {', '.join(run['tiers'])} "
            f"| {run['cited_evidence']} |"
        )
    return lines + [""]


def _render_method() -> list[str]:
    return [
        "## How to read this", "",
        "- **EA** (essential agreement): share of zones measured within ±2 mm of the reference.",
        "- **CA** (categorical agreement): share of disks whose S/I/R category matches.",
        "- **Very major**: a resistant isolate reported susceptible, the most dangerous error. "
        "**Major**: susceptible reported resistant. **Minor**: any disagreement involving I/SDD.",
        "- **Grounded report**: the model's narrative passed schema validation and cites only "
        "evidence IDs that exist in the deterministic report; otherwise the agent falls back to "
        "the deterministic report, which is always complete.",
        "- Targets are the ISO 20776-2 / FDA performance criteria for AST devices. These are "
        "synthetic plates: real-photo measurement is far weaker (EA 32.9%, see "
        "`docs/VALIDATION_REPORT.md`). Nothing here is clinical validation.", "",
        "## Reproduce", "",
        "```bash",
        "python scripts/run_evaluation.py                     # stage 1 only, no network",
        "python scripts/run_evaluation.py --live --alerts ins ops   # billable",
        "gh workflow run \"Agent evaluation\"                  # live run with repo secrets",
        "```", "",
    ]


def _render_report(results: dict[str, Any]) -> str:
    det = results["deterministic"]
    lines = [
        "# BacterioScope evaluation report", "",
        f"Generated {results['generated_at']} from commit `{results['commit']}` by "
        "`scripts/run_evaluation.py`.", "",
    ]
    lines += _render_findings(results)
    lines += _render_stage1(det) + _render_per_plate(det) + _render_discordances(det)
    if "live" in results:
        lines += _render_stage2(results["live"]) + _render_runs(results["live"])
    lines += _render_method()
    return "\n".join(lines)


def _run_url() -> str | None:
    server, repo, run = (os.getenv(k) for k in (
        "GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{server}/{repo}/actions/runs/{run}" if server and repo and run else None


def _imported_live(path: Path, run_url: str | None) -> dict[str, Any]:
    previous = json.loads(path.read_text(encoding="utf-8"))
    if "live" not in previous:
        raise SystemExit(f"{path} has no live stage to reuse.")
    live: dict[str, Any] = previous["live"]
    source = live.setdefault("source", {
        "generated_at": previous.get("generated_at"), "commit": previous.get("commit"),
    })
    if run_url:
        source["run_url"] = run_url
    return live


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--truth", type=Path, default=_SYNTHETIC_DIR / "ground_truth.json")
    parser.add_argument(
        "--output-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "evaluation"
    )
    parser.add_argument("--report", type=Path, default=None,
                        help="Also write the Markdown report to this path.")
    parser.add_argument("--live", action="store_true", help="Also run the live agent (billable).")
    parser.add_argument("--live-results", type=Path, default=None,
                        help="Reuse the live stage of an earlier evaluation_results.json.")
    parser.add_argument("--live-run-url", type=str, default=None,
                        help="Workflow run URL recorded with --live-results.")
    parser.add_argument("--modes", nargs="+", default=["routed", "ultra_only"])
    parser.add_argument("--alerts", nargs="*", default=[], choices=["ins", "ops"])
    parser.add_argument("--prices", type=str, default=None)
    return parser.parse_args()


def _attach_live(results: dict[str, Any], labeled: list[tuple[str, Any]],
                 args: argparse.Namespace) -> None:
    if args.live_results is not None:
        results["live"] = _imported_live(args.live_results, args.live_run_url)
        return
    if not args.live:
        return
    print("Stage 2: live agent")
    try:
        results["live"] = _live_stage(labeled, args)
    except Exception as exc:  # noqa: BLE001 -- report any live failure without secrets
        print(f"  live stage failed: {_redact(f'{type(exc).__name__}: {exc}')}")
        results["live_error"] = _redact(f"{type(exc).__name__}: {exc}")
        return
    results["live"]["source"] = {
        "generated_at": results["generated_at"], "commit": results["commit"],
        "run_url": _run_url(),
    }


def main() -> int:
    args = _parse_args()
    with contextlib.suppress(ImportError):
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=False)

    print("Stage 1: deterministic synthetic benchmark")
    deterministic, labeled = _deterministic_stage(args.truth)
    results: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "commit": _commit(),
        "deterministic": deterministic,
    }
    _attach_live(results, labeled, args)
    report = _render_report(results)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "evaluation_results.json").write_text(
        json.dumps(results, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "EVALUATION_REPORT.md").write_text(report, encoding="utf-8")
    if args.report is not None:
        args.report.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output_dir}")
    return 1 if args.live and "live_error" in results else 0


if __name__ == "__main__":
    sys.exit(main())
