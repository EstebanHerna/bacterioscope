# Nebius deployment

How to build the image, publish it, and run the live evaluation (`scripts/run_evaluation.py --live`) as a Nebius AI Studio Serverless Job instead of on a local machine. For the GitHub Actions path that already runs the same script directly on a GitHub-hosted runner, see `.github/workflows/agent-eval.yml` and the "GitHub Actions secrets" section below -- this document adds a second, optional execution path on Nebius infrastructure, not a replacement for it.

## What is confirmed vs. best-effort

Checked against Nebius's public CLI reference on 2026-10-19 (`docs.nebius.com/cli/reference/ai/job/create`, `.../ai/job/run`, `docs.nebius.com/serverless/jobs/manage`, `docs.nebius.com/serverless/quickstart/jobs`):

**Confirmed, used as-is below:**
- `nebius ai job create` runs a container image as a one-off batch job on a Compute VM, billed only while running.
- Flags: `--image` (`registry/path:tag` or `registry/path@digest`), `--container-command`, `--args`, `--env` (`KEY=VALUE`, repeatable), `--platform`, `--preset`, `--timeout` (1h-168h, default 24h), `--restart-policy` (`never` default, or `on-failure`), `--registry-username`, `--registry-password`.
- External registries, including GitHub Container Registry, are supported for `--image`; images from a private registry need `--registry-username`/`--registry-password`.

**Not confirmed -- do not trust blindly:**
- No example in any fetched page names a CPU-only `--platform` value. Every documented example (`gpu-h100-sxm`, `gpu-h200-sxm`, `gpu-l40s-a`, `gpu-l40s-d`) is a GPU platform, and `--platform` defaults to `gpu-h100-sxm`/`gpu-h200-sxm` if omitted. This evaluation job only makes outbound HTTPS calls to Nebius Token Factory and Tavily -- it needs no GPU -- but the docs never show a cheaper alternative, so `scripts/run_nebius_eval_job.py` makes `--platform`/`--preset` required arguments instead of guessing one. Check the Nebius console or `nebius ai job create --help` for the cheapest real option before running; this is a real cost risk, not a formality.
- Nebius also documents a native secret store referenced by an `--env-secret KEY=SECRET_SELECTOR` flag, but two separate documentation fetches describing it used different, inconsistent names for the underlying feature. Given that inconsistency, this setup does not depend on it: secrets are forwarded from the calling shell's own environment via the confirmed `--env` flag instead (see below).
- `nebius ai job run` (packages a local Python script onto a fresh VM, default image `python:3.12-slim`) is a different, simpler workflow than `job create` and is not what this document uses, since the goal is to run the existing Docker image, not a bare script.

## 1. Build and publish the image

The repository's single `Dockerfile` already serves both the API and this batch job (see its final comment); no second Dockerfile is needed.

```bash
docker build -t ghcr.io/estebanherna/bacterioscope:latest .
docker push ghcr.io/estebanherna/bacterioscope:latest
```

`docs/ROADMAP.md` (Phase F4) names this same GHCR path as the project's publish target; `scripts/run_nebius_eval_job.py --image` defaults to it. Nebius pulls from GHCR as an external registry -- pass `--registry-username`/`--registry-password` (a GitHub username and a PAT with `read:packages`, or `$GITHUB_TOKEN` in CI) if the package is private.

## 2. Run the job

```bash
pip install -e ".[dev]"  # or however the nebius CLI is installed/authenticated (nebius init)

python scripts/run_nebius_eval_job.py \
  --platform <confirm in the Nebius console; see caveat above> \
  --preset   <cheapest preset for that platform> \
  --execute
```

Without `--execute` the script only prints the assembled `nebius ai job create` command (secrets masked) -- use this to review before spending anything. The script fails fast if any of the required environment variables below are missing, and overrides the image's default `CMD` with `python scripts/run_evaluation.py --live --output-dir /tmp/eval --modes ... --alerts ...`, exactly as the Dockerfile's comment prescribes.

A self-check that needs no Nebius CLI or network access: `python scripts/run_nebius_eval_job.py --self-check`.

## 3. Required environment variables / secrets

Same names `scripts/run_evaluation.py` and `.github/workflows/agent-eval.yml` already use -- nothing new introduced here:

| Name | Kind | Source |
|---|---|---|
| `NEBIUS_API_KEY` | secret | Nebius Token Factory console |
| `TAVILY_API_KEY` | secret | Tavily account |
| `NEBIUS_MODEL_NANO` | plain value | Model ID from Nebius Token Factory |
| `NEBIUS_MODEL_SUPER` | plain value | Model ID from Nebius Token Factory |
| `NEBIUS_MODEL_ULTRA` | plain value | Model ID from Nebius Token Factory |

`scripts/run_nebius_eval_job.py` reads all five from the calling shell's environment and forwards them to the job with `--env`; it never writes them to a file. `scripts/run_evaluation.py` itself never prints their values (see its `_redact` helper).

## 4. GitHub Actions secrets (for `agent-eval.yml`)

Not documented elsewhere in `docs/` (checked `EVALUATION_HARNESS.md`, `HANDOFF.md`, `TEAM_EXECUTION_PLAN.md`, `SUBMISSION_KIT.md` first). To let someone with write access run `.github/workflows/agent-eval.yml` (`workflow_dispatch` only, never on `pull_request`):

1. GitHub repo -> **Settings** -> **Secrets and variables** -> **Actions**.
2. Under **Secrets**, add repository secrets `NEBIUS_API_KEY` and `TAVILY_API_KEY`.
3. Under **Variables**, add repository variables `NEBIUS_MODEL_NANO`, `NEBIUS_MODEL_SUPER`, `NEBIUS_MODEL_ULTRA` (model IDs, not secret, hence variables rather than secrets -- matching the workflow's existing `vars.*` references).
4. Run the workflow from the **Actions** tab -> "Agent evaluation" -> **Run workflow**.

`.github/workflows/agent-eval.yml` was checked against this and is already coherent with these names; it was not modified.

## 5. Results

The routed-vs-Ultra cost/latency/token comparison this job produces already has a real run documented -- see the table in `docs/EVALUATION_REPORT.md` and the "Numbers we can stand behind" section of `docs/HANDOFF.md` (16/16 grounded, 0.74x Ultra's output tokens, median ~2.5s). This document only covers how to run the job again, not a new set of numbers.

`evaluation_results.json` and `EVALUATION_REPORT.md` are written to `/tmp/eval` inside the container, which is not persisted by `nebius ai job create` on its own. Until a Nebius volume or object-storage target is wired up (`--volume`, not covered by this setup since no persistent Nebius storage resource exists yet for this project), retrieve them from the job's logs or `nebius ai job` log-streaming rather than assuming a file lands somewhere automatically.
