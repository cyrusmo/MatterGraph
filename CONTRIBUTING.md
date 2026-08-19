# Contributing to MatterGraph

Thanks for your interest. MatterGraph is an early-stage, Apache-2.0 project focused on **clear data models**, **reproducible examples**, and **small, reviewable** pull requests.

## Development setup

- Python 3.10+ (tested in CI on 3.10–3.12)
- [uv](https://docs.astral.sh/uv/) for dependency and workspace management
- `uv.lock` is the canonical lockfile for this repository (no `poetry.lock` in the default workflow)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync --all-packages --group dev
```

Run checks:

```bash
uv run ruff check .
uv run pytest
cd apps/web && npm ci && npm test && npm run build && npm run test:e2e
```

## Public extension rails

- **Schema evolution:** edit the Pydantic model first, keep changes additive under `0.1`, run
  `python scripts/generate_schemas.py`, and add a backward-compatibility fixture plus parity test.
  Reviewer approval, requirements, qualification, proprietary scores, and decision linkage do
  not belong in public contracts.
- **Connectors:** implement `Connector`, accept `ConnectorQuery`, preserve source IDs and method
  provenance, and use `ConnectorHTTPPolicy` for HTTP paths. A connector must raise when it cannot
  honor a query; it must not silently return an empty result for an unsupported capability.
- **Contextual properties:** use `PropertyContext` for conditions and `SourceArtifact` for
  citation, revision, license, page, and checksum. Do not hide context in an opaque `extra` field
  when a typed public field exists.
- **Graph features:** preserve exact periodic offsets and Cartesian displacements, reciprocal
  edges, complete tied shells, no zero-distance self loops, and explicit disorder rejection.
  Summary endpoints must omit raw `node_features`, `edge_index`, and large tensors.
- **Result parsers:** produce `SimulationResultEnvelope` with engine/version, method, parameters,
  checksums, convergence, properties, artifacts, and provenance. Parser examples import results;
  they do not orchestrate simulators.

## Workspace packaging note

The root [`pyproject.toml`](https://github.com/cyrusmo/MatterGraph/blob/main/pyproject.toml) builds a tiny metapackage that pins workspace dependencies.
[`_workspace_meta.py`](https://github.com/cyrusmo/MatterGraph/blob/main/_workspace_meta.py) exists only for that setuptools metapackage shim.

## Pull requests

- One logical change per PR; link an issue when possible
- Add or update tests for behavior changes
- Do not commit large datasets, API secrets, or proprietary material

## What we merge first

- Bug fixes, schema improvements, and connector robustness
- Docs and examples that make the v0.1 story obvious
- Performance work with benchmarks or clear motivation

## Code of conduct

See [CODE_OF_CONDUCT.md](https://github.com/cyrusmo/MatterGraph/blob/main/CODE_OF_CONDUCT.md).
