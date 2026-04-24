# Getting started

1. Clone the repository and create a virtual environment (see the root [README](../README.md)).
2. `uv sync --all-packages --group dev`
3. Point the demo API at `data/demo/materials_sample.jsonl` (default) or your own JSONL in the `Material` shape.
4. From the repository root, after `uv sync`, run: `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` (the `mattergraph-api` package is installed in editable mode, so the `app` module resolves from `packages/mattergraph-api`.)
5. Open the web app under `apps/web` (see that folder’s [README](../apps/web/README.md)).

**Materials Project API:** set a 32-character key in `MP_API_KEY` (preferred) or `MATERIALS_PROJECT_API_KEY` for `MaterialsProjectConnector`.
