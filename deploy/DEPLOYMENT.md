# Public deployment (Persona 4)

How to put the BacterioScope demo on a public URL with the provider keys held as
platform secrets, outside the repository, logs, and browser bundle. The image
listens on port 8000 and starts uvicorn by default (`Dockerfile`).

Coordinate the go/no-go with Esteban: the demo spends Token Factory credit on
his account on every review.

## What ships

- `Dockerfile` (repository root): the FastAPI image. Serves the light-box UI at
  `/`, the stable `POST /analyze`, and the `/api/*` review endpoints.
- `deploy/huggingface/README.md`: Space metadata and setup for a Docker SDK
  Space on Hugging Face.
- `deploy/render.yaml`: a Render blueprint that builds the same Dockerfile.

Any host that runs one Docker image on one port works (Hugging Face Spaces
Docker, Render, Fly.io, a small VM). Pick one; the rest are alternatives.

## Secrets

Two keys, both server-side only:

| Secret | Purpose | Without it |
|---|---|---|
| `NEBIUS_API_KEY` | Nemotron via Token Factory | Review returns the complete deterministic report with `status: fallback`, `fallback_reason: token_factory_unavailable`. |
| `TAVILY_API_KEY` | INS/PAHO public-alert search | Alerts return unavailable; plate review continues. |

Rules:

- Set them in the host's secret store, not in `.env`, not in the image, not in
  any committed file. `.env` stays gitignored.
- Never echo key values into logs, screenshots, or the recorded demo.
- CI already runs gitleaks on every push; keep it green.

## Hugging Face Spaces (Docker)

1. Create a Docker SDK Space.
2. Put the front matter from `deploy/huggingface/README.md` at the top of the
   Space `README.md` (keep `app_port: 8000`).
3. Space settings -> Variables and secrets -> add `NEBIUS_API_KEY` and
   `TAVILY_API_KEY` as secrets.
4. Push the repo to the Space and let it build. The Space URL serves the light
   box.

## Render

1. New -> Blueprint, point it at the repo; Render reads `deploy/render.yaml`.
2. Fill `NEBIUS_API_KEY` and `TAVILY_API_KEY` when prompted (the blueprint marks
   them `sync: false`, so values are entered in the dashboard only).
3. Deploy. Health check is `GET /`.

## Smoke check after deploy

1. Open `/?sample=plate_mixed_sir&lang=en`; confirm disks and zones render.
2. Run a review with alerts on; confirm a `grounded` status and that citations
   resolve.
3. Temporarily confirm the fallback path by checking a review still returns the
   deterministic report if the model is unavailable.
4. Confirm `POST /analyze` still returns its stable contract (do not change it).

## Operational notes

- Single worker only: sessions are in-memory (LRU of 48) and not shared.
- Only bundled samples and non-identifiable photos on a public instance.
- Watch Token Factory usage; add a per-IP limit if the link spreads.
- Keep the strict CSP; no `unsafe-inline`.
