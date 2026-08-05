# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the project is pre-1.0, minor versions may contain breaking changes to the
Python API. Breaking changes are always listed under **Changed** or **Removed**.

## [Unreleased]

### Added

- `py.typed` markers in all five distributed packages, so downstream consumers
  get the type information the codebase already carries.
- `mattergraph.graph` now has an explicit `__init__.py` re-exporting
  `CrystalGraph`, `CrystalGraphBuilder`, and the atom/edge feature helpers,
  matching every sibling subpackage.
- Per-package READMEs, keywords, classifiers, and project URLs so each
  distribution has a usable PyPI landing page.
- `Release` workflow: tag-triggered build and publish to PyPI via Trusted
  Publishing (OIDC), with a TestPyPI rehearsal path via `workflow_dispatch`,
  a tag/version consistency check, and `twine check` metadata validation.
- CI now runs the test suite on Python 3.10, 3.11, and 3.12 — the range
  `requires-python` has always claimed — and builds wheels on every push so
  packaging breakage surfaces before tag time.
- Coverage reporting is enabled with a 70% floor (current coverage is ~74%).

### Changed

- **Breaking:** the API package's importable module was renamed from `app` to
  `mattergraph_api`. A top-level `app` module is far too generic to publish to
  PyPI, where it would collide with unrelated projects. Update
  `uvicorn app.main:app` to `uvicorn mattergraph_api.main:app`, and
  `from app.services import ...` to `from mattergraph_api.services import ...`.
- CI workflows consolidated: `tests.yml` and `lint.yml` were removed because
  they re-ran the same checks already in `ci.yml`. `ci.yml` now triggers on all
  branches, so branch pushes keep getting feedback.
- `SECURITY.md` now names an actual reporting channel.

## [0.1.0] - Unreleased

Initial public surface.

### Added

- **Schema** — `Material`, `MaterialProperty`, `ProvenanceRecord`,
  `CrystalStructure`, and `SimulationJobRef` as strict Pydantic v2 models, with
  matching JSON Schemas under `data/schemas/`.
- **Normalization** — unit conversion for energy, length, pressure, density, and
  temperature; formula standardization; canonical property names across six
  properties (density, formation energy per atom, energy above hull, bulk
  modulus, shear modulus, band gap).
- **Connectors** — Materials Project, JARVIS-DFT, NOMAD public metadata,
  LeMat-Bulk companion adapter, and local CSV. OQMD ships as a stub that
  preserves the API surface.
- **Workflow layer** — `MatterGraphDataset` with chainable, audited filters and
  `CandidateSlice` with content-hashed, reproducible slice IDs. Guardrails block
  mixed XC functionals and duplicate records unless explicitly overridden.
- **Crystal graphs** — `CrystalGraphBuilder` producing periodic neighbor graphs
  with 103-column atom features, emitted as plain NumPy.
- **Scoring** — a transparent `Scorecard` baseline (min–max normalized
  objectives plus hard constraints), explicitly documented as a toy rather than
  a production decision engine.
- **Benchmarks** — discovery ranking metrics, uncertainty coverage, stratified
  validation splits, and an optional Matbench adapter.
- **Simulation** — validated ASE job specs with a working EMT relaxation runner;
  LAMMPS and Quantum ESPRESSO entry points ship as structured-failure stubs.
- **API** — FastAPI demo exposing `/materials`, `/search`, `/scores/rank`,
  `/simulations/ase/relax`, and `/workflows/lematerial/demo`.
- **Web** — a React workbench with material table, comparison view, constraint
  panel, and simulation queue.
- **Docs and examples** — nine documentation pages, ten LeMaterial SQL
  cookbook recipes, seven numbered example scripts, and an underwater-drone
  screening template.

[Unreleased]: https://github.com/cyrusmo/MatterGraph/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cyrusmo/MatterGraph/releases/tag/v0.1.0
