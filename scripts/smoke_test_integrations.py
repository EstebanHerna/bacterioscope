"""Check local Nebius Token Factory and Tavily setup without exposing secrets.

Run from any directory with ``python scripts/smoke_test_integrations.py``.
The default run makes one fixed Tavily query for each official source. Add
``--check-inference`` to send one short, non-clinical Nano inference request.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def _safe_error(exc: Exception) -> str:
    """Return an error summary with configured credentials removed."""
    message = str(exc)
    for name in ("NEBIUS_API_KEY", "TAVILY_API_KEY"):
        secret = os.getenv(name, "")
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return f"{type(exc).__name__}: {message[:240]}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-tavily",
        action="store_true",
        help="Skip the two live Tavily searches.",
    )
    parser.add_argument(
        "--check-inference",
        action="store_true",
        help="Send one short, non-clinical request to Nemotron Nano (billable).",
    )
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
    except ImportError:
        print("Missing dependency: run `python -m pip install -e '.[agent]'`.")
        return 1

    load_dotenv(REPO_ROOT / ".env", override=False)
    failures = 0

    from bacterioscope.agent.nemotron_client import TokenFactoryClient
    from bacterioscope.integrations.tavily import TavilyAlertSearch

    missing = [
        name
        for name in ("NEBIUS_API_KEY", "TAVILY_API_KEY")
        if not os.getenv(name, "").strip()
    ]
    if missing:
        failures += len(missing)
        print("Missing required .env setting(s): " + ", ".join(missing))
    else:
        print("Provider credentials: configured (values hidden)")

    token_factory = TokenFactoryClient()
    visible_models: set[str] = set()
    if token_factory.configured:
        try:
            visible_models = set(token_factory.list_models())
            nemotron = sorted(model for model in visible_models if "nemotron" in model.casefold())
            print(f"Nebius Token Factory: authenticated; {len(visible_models)} model(s) visible")
            print("Nemotron IDs in account catalog:")
            for model in nemotron:
                print(f"  - {model}")
            for tier in ("NANO", "SUPER", "ULTRA"):
                env_name = f"NEBIUS_MODEL_{tier}"
                model = os.getenv(env_name, "").strip()
                if not model:
                    failures += 1
                    print(f"  MISSING {env_name}")
                elif model not in visible_models:
                    failures += 1
                    print(f"  UNAVAILABLE {env_name}: {model}")
                else:
                    print(f"  OK {env_name}: {model}")
        except Exception as exc:  # live provider/network failures are actionable output
            failures += 1
            print("Nebius Token Factory: FAILED — " + _safe_error(exc))
    else:
        print("Nebius Token Factory: SKIPPED; NEBIUS_API_KEY is missing")

    if args.check_inference:
        if not token_factory.configured or "NEBIUS_MODEL_NANO" not in os.environ:
            failures += 1
            print("Nemotron Nano inference: FAILED — configure the key and Nano model ID first")
        else:
            try:
                completion = token_factory.chat(
                    "nano",
                    [{"role": "user", "content": "Reply with exactly: OK"}],
                    max_tokens=64,
                )
                if completion.content.strip():
                    print(
                        "Nemotron Nano inference: OK; "
                        f"model={completion.model}; response received"
                    )
                else:
                    failures += 1
                    print("Nemotron Nano inference: FAILED — empty response")
            except Exception as exc:  # live provider/network failures are actionable output
                failures += 1
                print("Nemotron Nano inference: FAILED — " + _safe_error(exc))

    if not args.skip_tavily:
        tavily = TavilyAlertSearch(max_results=1, timeout_seconds=20)
        if not tavily.configured:
            failures += 1
            print("Tavily: SKIPPED; TAVILY_API_KEY is missing")
        else:
            for source in ("ins", "ops"):
                try:
                    alerts = tavily.search_amr_alerts(source)
                    print(f"Tavily {source.upper()}: OK; {len(alerts)} eligible official result(s)")
                    for alert in alerts:
                        print(f"  - {alert.title[:120]} — {alert.url}")
                except Exception as exc:  # live provider/network failures are actionable output
                    failures += 1
                    print(f"Tavily {source.upper()}: FAILED — {_safe_error(exc)}")
    else:
        print("Tavily: skipped by request")

    if failures:
        print(f"\nSetup check finished with {failures} issue(s).")
        return 1
    print("\nSetup check finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
