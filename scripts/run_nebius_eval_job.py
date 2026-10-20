"""Launch the BacterioScope live evaluation as a Nebius AI Studio Serverless Job.

Wraps ``nebius ai job create`` (Nebius CLI; see
https://docs.nebius.com/cli/reference/ai/job/create) to run the existing Docker
image's batch-evaluation command -- ``python scripts/run_evaluation.py --live
--output-dir /tmp/eval`` (see the Dockerfile's final comment) -- on Nebius compute
instead of a local machine. This is an alternative execution path to
``.github/workflows/agent-eval.yml``, which already runs the same script directly
on a GitHub-hosted runner; use this script when a run needs to live on Nebius
infrastructure instead (longer timeout than a GitHub Actions job, no Actions
minutes spent, or a future GPU-backed stage).

Requires the ``nebius`` CLI installed and authenticated (``nebius init``) -- this
script does not manage Nebius account credentials, only assembles and runs the
``job create`` command.

Confirmed against Nebius CLI docs (checked 2026-10-19): ``--image``,
``--container-command``, ``--args``, ``--env``, ``--platform``, ``--preset``,
``--timeout``, ``--restart-policy``, ``--registry-username``,
``--registry-password``.

Not confirmed: no CPU-only ``--platform`` value appears in any public Nebius
example found (only GPU platforms: ``gpu-h100-sxm``, ``gpu-h200-sxm``,
``gpu-l40s-a``, ``gpu-l40s-d``). This evaluation job only makes outbound API
calls and needs no GPU, but the docs never show a non-GPU platform name, so
``--platform``/``--preset`` are required arguments here instead of a guessed
default -- confirm the cheapest available platform in the Nebius console or
``nebius ai job create --help`` before running. The exact name and selector
format of Nebius's own secret store (``--env-secret``) was reported
inconsistently across documentation fetches, so this script does not depend on
it; secrets are forwarded instead from the calling shell's environment via
``--env``, the one mechanism confirmed stable and documented. See
docs/NEBIUS_DEPLOYMENT.md for the full writeup.
"""

from __future__ import annotations

import argparse
import os
import subprocess  # nosec B404
import sys
from datetime import datetime, timezone

_REQUIRED_SECRETS = ("NEBIUS_API_KEY", "TAVILY_API_KEY")
_REQUIRED_VARS = ("NEBIUS_MODEL_NANO", "NEBIUS_MODEL_SUPER", "NEBIUS_MODEL_ULTRA")


def _redact(command: list[str], extra_secrets: tuple[str | None, ...] = ()) -> list[str]:
    """Mask secret env values and any extra secret strings (e.g. a registry
    password) so the printed command is safe to log, in dry-run or otherwise."""
    redacted = list(command)
    secrets = [os.environ.get(name, "") for name in _REQUIRED_SECRETS] + list(extra_secrets)
    for value in secrets:
        if not value:
            continue
        redacted = [part.replace(value, "***") for part in redacted]
    return redacted


def _missing_env(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not os.environ.get(name)]


def build_command(args: argparse.Namespace) -> list[str]:
    """Assemble the `nebius ai job create` argv for this evaluation job."""
    eval_args = (
        f"scripts/run_evaluation.py --live --output-dir /tmp/eval "
        f"--modes {' '.join(args.modes)}"
    )
    if args.alerts:
        eval_args += f" --alerts {' '.join(args.alerts)}"

    command = [
        "nebius", "ai", "job", "create",
        "--name", f"bacterioscope-eval-{datetime.now(timezone.utc):%Y%m%d%H%M%S}",
        "--image", args.image,
        "--container-command", "python",
        "--args", eval_args,
        "--platform", args.platform,
        "--preset", args.preset,
        "--timeout", args.timeout,
        "--restart-policy", "never",
    ]
    for name in _REQUIRED_SECRETS + _REQUIRED_VARS:
        command += ["--env", f"{name}={os.environ[name]}"]
    if args.registry_username and args.registry_password:
        command += [
            "--registry-username", args.registry_username,
            "--registry-password", args.registry_password,
        ]
    return command


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_image = os.environ.get("NEBIUS_EVAL_IMAGE", "ghcr.io/estebanherna/bacterioscope:latest")
    parser.add_argument(
        "--image",
        default=default_image,
        help="Docker image reference. Default matches docs/ROADMAP.md's GHCR target.",
    )
    parser.add_argument(
        "--platform",
        required=True,
        help="Nebius compute platform, e.g. gpu-l40s-d (no CPU-only platform is "
        "confirmed in public docs; see module docstring).",
    )
    parser.add_argument(
        "--preset", required=True, help="Resource preset for --platform, e.g. 1gpu-8vcpu-32gb."
    )
    parser.add_argument(
        "--timeout", default="1h", help="Job wall-clock limit (Nebius accepts 1h-168h)."
    )
    parser.add_argument("--modes", nargs="+", default=["routed", "ultra_only"])
    parser.add_argument("--alerts", nargs="*", default=["ins", "ops"], choices=["ins", "ops"])
    parser.add_argument("--registry-username", default=os.environ.get("GHCR_USERNAME"))
    parser.add_argument("--registry-password", default=os.environ.get("GHCR_TOKEN"))
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually submit the job. Without this flag, only print the command.",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args()
    missing = _missing_env(_REQUIRED_SECRETS + _REQUIRED_VARS)
    if missing:
        print(f"Missing required environment variables: {', '.join(missing)}", file=sys.stderr)
        return 1

    command = build_command(args)
    extra_secrets = (args.registry_password, args.registry_username)
    print("Command:", " ".join(_redact(command, extra_secrets)))
    if not args.execute:
        print("Dry run (no job submitted). Pass --execute to submit it.")
        return 0

    result = subprocess.run(command, check=False)  # nosec B603
    return result.returncode


def _self_check() -> None:
    """Minimal assert-based check: run with `--self-check`, no Nebius CLI needed."""
    os.environ.update(
        NEBIUS_API_KEY="secret-key",
        TAVILY_API_KEY="secret-tavily",
        NEBIUS_MODEL_NANO="nano-id",
        NEBIUS_MODEL_SUPER="super-id",
        NEBIUS_MODEL_ULTRA="ultra-id",
    )
    args = _parse_args(
        [
            "--platform", "gpu-l40s-d",
            "--preset", "1gpu-8vcpu-32gb",
            "--registry-username", "octocat",
            "--registry-password", "ghp_realtoken123",
        ]
    )
    command = build_command(args)
    assert "--image" in command
    assert command[command.index("--image") + 1] == "ghcr.io/estebanherna/bacterioscope:latest"
    assert command.count("--env") == len(_REQUIRED_SECRETS) + len(_REQUIRED_VARS)
    assert "ghp_realtoken123" in command  # real value still used for --execute
    redacted = _redact(command, (args.registry_password, args.registry_username))
    joined = " ".join(redacted)
    assert "secret-key" not in joined
    assert "secret-tavily" not in joined
    assert "ghp_realtoken123" not in joined
    assert "octocat" not in joined
    assert _missing_env(("NEBIUS_API_KEY", "DOES_NOT_EXIST_VAR")) == ["DOES_NOT_EXIST_VAR"]
    print("self-check ok")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _self_check()
        sys.exit(0)
    sys.exit(main())
