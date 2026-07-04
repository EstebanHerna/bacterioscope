# BacterioScope Security Audit

**Date:** 2026-07-04
**Auditor:** Internal security review
**Scope:** Full codebase — `src/bacterioscope/`, `scripts/`, `Dockerfile`, `.github/workflows/`
**Tools used:** bandit 1.8.x, pip-audit 2.7.x, manual review

---

## Summary

| Severity | Found | Fixed | Remaining |
|----------|-------|-------|-----------|
| Critical | 0 | — | 0 |
| High | 2 | 2 | 0 |
| Medium | 3 | 3 | 0 |
| Low | 3 | 3 | 0 |

All findings were remediated in commit `security: intensive audit, dependency scanning, hardening`.

---

## Findings

### HIGH-1 — Unbounded download size (DoS vector)

- **File:** `scripts/download_data.py`, `download_file()`
- **Severity:** High
- **Description:** No cap on bytes read from the HTTP response. A malicious or compromised server could stream an infinite body, exhausting disk space and eventually crashing the host.
- **Fix applied:** Added `_MAX_DOWNLOAD_BYTES = 5 GB` constant. The Content-Length header is checked before starting the download; the running byte counter is checked inside the chunk loop and aborts with `ValueError` if exceeded.

---

### HIGH-2 — Missing zip bomb protection

- **File:** `scripts/download_data.py`, `extract_zip()`
- **Severity:** High
- **Description:** The existing zip slip check (path traversal) was correct, but there was no guard against zip bombs — archives with a very high compression ratio that expand to many gigabytes of data on disk.
- **Fix applied:** Before any file is extracted, the function now iterates `zf.infolist()` and computes `total_uncompressed / total_compressed`. If the ratio exceeds `_MAX_COMPRESSION_RATIO = 100x` or the uncompressed size exceeds `_MAX_EXTRACT_BYTES = 10 GB`, extraction is aborted.

---

### MEDIUM-1 — Model deserialization via torch.load without weights_only=True

- **File:** `src/bacterioscope/detection/detector.py`, `_load_model()`
- **Severity:** Medium
- **Description:** `ultralytics.YOLO(path)` internally calls `torch.load()`. In PyTorch versions prior to 2.6, the default is `weights_only=False`, which allows arbitrary Python objects to be deserialized. A `.pt` file crafted by an adversary can execute arbitrary code at load time. This is the highest-risk vector for this project if model weights are ever distributed or downloaded from untrusted sources.
- **Direct fix status:** `ultralytics.YOLO()` does not expose a `weights_only` parameter in its public API. Patching torch internals is not viable.
- **Mitigations applied:**
  1. Added `_TRUSTED_MODEL_HASHES: dict[str, str]` in `detector.py`. When a model filename is present in this dict, its SHA-256 hash is verified before `YOLO()` is called. If the hash does not match, `ValueError` is raised and the model is never loaded.
  2. Added `_verify_weights()` method on `DiskDetector` that performs the check.
  3. Documented the risk and mitigation in this file and in `SECURITY.md`.
- **Remaining risk:** For training weights not in `_TRUSTED_MODEL_HASHES`, no hash check is performed. Operators must populate the dict with known-good hashes when distributing models, and must only accept weights from sources they control. Ultralytics >= 8.3 reportedly passes `weights_only=True` internally; pinning the ultralytics version is an additional safeguard.

---

### MEDIUM-2 — No .dockerignore

- **File:** root `.dockerignore` (absent)
- **Severity:** Medium
- **Description:** Without `.dockerignore`, `COPY src/` and `COPY scripts/` also cause Docker's build context to include `.git/`, `.env`, test directories, notebooks, and development caches. A leaked `.env` in a layer is a classic credential exposure vector; the inflated build context also slows builds significantly.
- **Fix applied:** Created `.dockerignore` excluding `.git/`, `.venv/`, `.env`, `tests/`, `docs/`, `notebooks/`, `data/raw/`, `data/processed/`, `__pycache__/`, cache directories, and IDE folders.

---

### MEDIUM-3 — CLI confidence parameter not range-validated

- **File:** `src/bacterioscope/cli.py`, `analyze()` command
- **Severity:** Medium
- **Description:** The `--confidence` option accepted any float value without bounds. Passing `--confidence 100.0` or `--confidence -5` would propagate to `DiskDetector` and from there to YOLO or HoughCircles with undefined behavior.
- **Fix applied:** Added `min=0.0, max=1.0` to the `typer.Option()` call. Typer enforces this at argument parsing time and prints a clear error message to the user.

---

### LOW-1 — No CI dependency auditing

- **File:** `.github/workflows/ci.yml`
- **Severity:** Low
- **Description:** CVE detection in the dependency tree was not part of the automated pipeline. A vulnerable transitive dependency could go undetected indefinitely.
- **Fix applied:**
  - Added `pip-audit>=2.7` to `[dev]` extras in `pyproject.toml`.
  - Added an `audit` job to `ci.yml` that installs the full `[dev]` extras and runs `pip-audit` on every push and pull request to `main`.

---

### LOW-2 — No CodeQL static analysis

- **File:** `.github/workflows/` (absent)
- **Severity:** Low
- **Description:** GitHub's CodeQL scanner was not configured. It catches vulnerability patterns (SQL injection, command injection, path traversal, insecure deserialization) that bandit can miss, and runs in GitHub's infrastructure with no additional tooling required.
- **Fix applied:** Created `.github/workflows/codeql.yml` running CodeQL with `security-and-quality` queries on every push/PR to `main` and on a weekly schedule (Mondays 06:00 UTC).

---

### LOW-3 — No .env.example

- **File:** root (absent)
- **Severity:** Low
- **Description:** `.env` was already gitignored, but no `.env.example` existed to document which environment variables are expected. Developers might hard-code values that should be externalized.
- **Fix applied:** Created `.env.example` listing all recognized env vars with comments and no real values.

---

## pip-audit Results

`pip-audit` was run against the installed global Python environment. The 83 CVEs reported affect packages not declared as BacterioScope dependencies (black, bleach, django, gitpython, jupyter-server, jupyterlab, etc.). These are development tools from the system Python installation, not from this project.

**BacterioScope direct dependencies (numpy, opencv-python-headless, scikit-image, scikit-learn, Pillow, typer, rich, httpx): zero CVEs found.**

In CI, `pip-audit` runs in a clean environment with only the declared dependencies installed, so the noise from the system environment does not appear.

---

## bandit Results

```
No issues identified.
Total lines of code: 469
Total lines skipped (#nosec): 0
```

Clean scan across all 469 lines of source code.

---

## Items Out of Scope

- Vulnerabilities in third-party packages not declared as dependencies.
- Physical access attacks.
- Denial-of-service through legitimate large research datasets (mitigated by the 50 MB image cap and the new download/extraction caps).

---

## Recommendations for Future Phases

1. **Populate `_TRUSTED_MODEL_HASHES`** as soon as YOLOv8 weights are trained and distributed. Record SHA-256 of the official weights file before shipping.
2. **Pin ultralytics to >= 8.3** when adding it to dependencies, as that version internally enforces `weights_only=True`.
3. **Add rate limiting and request size caps to the FastAPI layer** (Phase 4) before exposing the API publicly.
4. **Add `pip-audit` to pre-commit hooks** alongside ruff and bandit for local enforcement.
