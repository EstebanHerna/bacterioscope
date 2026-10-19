FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system bacterio \
    && adduser --system --ingroup bacterio bacterio

WORKDIR /app

# README.md is required by pyproject's `readme` field. docs/contracts/ holds
# the report schema agent/validator.py loads at runtime, panels/ the panel
# YAMLs PanelManager reads, and examples/synthetic/ the benchmark plates and
# their ground_truth.json. data/models/ is not copied: the weights are
# gitignored and the detector falls back to Hough without them.
COPY pyproject.toml README.md ./
COPY src/ src/
COPY scripts/ scripts/
COPY panels/ panels/
COPY docs/contracts/ docs/contracts/
COPY examples/synthetic/ examples/synthetic/
COPY examples/real/real_plate_box4.jpg examples/real/

RUN pip install --no-cache-dir -e ".[api,agent]" \
    && chown -R bacterio:bacterio /app

USER bacterio

EXPOSE 8000

# Default: the REST API. For a batch evaluation job (e.g. Nebius Serverless
# Jobs), override the command with:
#   python scripts/run_evaluation.py --live --output-dir /tmp/eval
CMD ["uvicorn", "bacterioscope.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
