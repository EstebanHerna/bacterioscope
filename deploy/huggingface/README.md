---
title: BacterioScope
emoji: microscope
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Read a Kirby-Bauer antibiogram plate from a photo, reviewed by a human.
---

# BacterioScope on Hugging Face Spaces

This Space runs the BacterioScope FastAPI image (the light-box review UI at `/`)
as a Docker SDK Space. The Space builds the repository `Dockerfile`, which
listens on port 8000; `app_port: 8000` above maps the Space to it.

## One-time setup

1. Create a Docker SDK Space and push this repository to it (or point the Space
   at the GitHub repo mirror).
2. Copy the `title`/`app_port` front matter above into the Space `README.md`.
   Hugging Face requires this metadata block at the top of the Space README.
3. Add the provider keys as **repository secrets** in the Space settings, never
   in the repository:
   - `NEBIUS_API_KEY`
   - `TAVILY_API_KEY`
   The container reads them from the environment at runtime; the review falls
   back to the complete deterministic report when `NEBIUS_API_KEY` is absent.
4. Restart the Space to pick up the secrets.

## Guardrails for a public instance

- Only bundled samples and non-identifiable photos may be used. Do not upload
  patient or institutional images.
- Every review spends Token Factory credit. Keep the alerts toggle optional and
  watch usage; add a per-IP limit if the link circulates widely.
- Sessions live in process memory (LRU of 48) and are not shared across workers.
  Run a single worker, which is the image default.
- Keep the strict CSP. Do not add `unsafe-inline`.

See `deploy/DEPLOYMENT.md` for the full checklist and the Render alternative.
