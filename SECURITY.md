# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report security issues by emailing **ea.hernandezs1@uniandes.edu.co** with the subject line `[BacterioScope SECURITY]`.

Include:
- A description of the vulnerability and its potential impact
- Steps to reproduce
- Any suggested mitigations

You will receive an acknowledgment within 72 hours. Confirmed vulnerabilities will be patched and disclosed via a GitHub Security Advisory.

## Security Measures

### Input validation
- Image files are validated against an allowlist of extensions (`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`) before being passed to OpenCV.
- A 50 MB file size cap prevents resource exhaustion via oversized inputs.
- The `--confidence` CLI option is bounded to [0.0, 1.0] at parse time.
- Zip archives extracted by `scripts/download_data.py` are validated for: path traversal (zip slip), compression ratio > 100x (zip bomb), and uncompressed size > 10 GB.
- HTTP downloads are capped at 5 GB regardless of Content-Length.

### Model weight integrity
Loading a `.pt` file with `torch.load` (called internally by ultralytics) can execute arbitrary Python code when `weights_only=False`. Mitigations:

- `DiskDetector` verifies the SHA-256 hash of any model file whose name appears in `_TRUSTED_MODEL_HASHES` before loading. Operators distributing known-good weights should populate this dict.
- Only load model weights from sources you control. Never accept `.pt` files from untrusted parties.
- Pinning `ultralytics >= 8.3` is recommended; that version enforces `weights_only=True` internally.

### Dependency management
- Heavy ML dependencies (`torch`, `ultralytics`) are optional extras — not installed in CI or lightweight deployments.
- `pip-audit` runs on every CI push to detect CVEs in the dependency tree.
- Run `pip-audit` periodically in development environments.

### Container
- The Docker image runs as a non-root system user (`bacterio`).
- `.dockerignore` prevents `.env`, `.git/`, test directories, and caches from entering the build context.

### Static analysis
- `bandit` runs on every CI push (zero findings as of 2026-07-04).
- `ruff` enforces code style rules.
- `mypy --strict` enforces type safety across the entire codebase.
- CodeQL runs on every push/PR and weekly, using the `security-and-quality` query suite.

## Out of Scope

- Vulnerabilities in third-party packages (report directly to their maintainers).
- Issues requiring physical access to the deployment environment.
- Denial-of-service via legitimate, extremely large datasets in research workflows.

## Security Audit

A full security audit was performed on 2026-07-04. See [`docs/SECURITY_AUDIT.md`](docs/SECURITY_AUDIT.md) for findings, severities, and applied remediations.
