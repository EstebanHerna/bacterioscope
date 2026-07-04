FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system bacterio \
    && adduser --system --ingroup bacterio bacterio

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
COPY scripts/ scripts/
COPY data/models/ data/models/

RUN pip install --no-cache-dir -e . \
    && chown -R bacterio:bacterio /app

USER bacterio

EXPOSE 8000

CMD ["uvicorn", "bacterioscope.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]
