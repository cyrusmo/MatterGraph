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
```

## Workspace packaging note

The root [`pyproject.toml`](pyproject.toml) builds a tiny metapackage that pins workspace dependencies.
[`_workspace_meta.py`](_workspace_meta.py) exists only for that setuptools metapackage shim.

## Pull requests

- One logical change per PR; link an issue when possible
- Add or update tests for behavior changes
- Do not commit large datasets, API secrets, or proprietary material

## What we merge first

- Bug fixes, schema improvements, and connector robustness
- Docs and examples that make the v0.1 story obvious
- Performance work with benchmarks or clear motivation

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
