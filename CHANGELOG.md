# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

While the project is pre-1.0, minor versions may contain breaking changes to the
Python API. Breaking changes are always listed under **Changed** or **Removed**.

## [Unreleased]

### Added

- `OptimadeConnector` reads any OPTIMADE provider, closing COD and OQMD and reaching
  AFLOW, Materials Project, NOMAD and ~18 others through one client with no new
  dependency. It handles four upstream behaviours verified against the live APIs:
  `response_fields` is mandatory (COD's default response omits all site data),
  `links.next` is a bare string on OQMD and a `{"href": ...}` object on COD,
  `species[].name` is a site label rather than an element symbol, and
  `cartesian_site_positions` must be converted to the fractional coordinates
  `CrystalStructure` stores.
- OPTIMADE records carry a density derived from the cell, labelled
  `method="derived"` — OPTIMADE standardizes no physical property, so without this
  the records would be unrankable. OQMD additionally supplies `band_gap`,
  `formation_energy_per_atom`, and `energy_above_hull`.
- `Scorecard.report()` reports `mixed_hull_conventions`, so a ranking column pooling
  OQMD hull distances with Materials Project `energy_above_hull` is detectable rather
  than silently biased.
- `Material.dimensionality` records the number of periodic dimensions. When it is
  not 3, no density is derived: a vacuum-padded slab's bulk density is a function of
  the padding, not a material property, and a `Scorecard` would rank it against real
  crystals without complaint.

- A connector contract in `mattergraph_connectors.base`: the `Connector` protocol,
  a `ConnectorQuery` model covering `elements` / `source_ids` / `properties` /
  `max_records` / `page_size`, and shared `connector_provenance()` and
  `apply_property_filter()` helpers. Every connector previously had its own `fetch`
  signature — four had already diverged — with nothing able to enforce or even
  enumerate the contract.
- Every ingested `Material` now carries a `ProvenanceRecord`. Materials Project,
  JARVIS, and NOMAD all left `Material.provenance` empty and put lineage in the
  untyped `metadata` dict, so nothing reasoning about provenance could see it.
- `ProvenanceRecord.parameters` records the settings behind a value (functional,
  dataset, calculator). Without it the schema could not express what produced a
  number, only that something had.
- `PropertyMethod.DERIVED` distinguishes a value MatterGraph computed from other
  fields on the same record from one whose method is genuinely unknown.
- `mattergraph-connectors` declares `[mp]`, `[jarvis]`, and `[all]` extras.

- `mattergraph.derived.elastic` derives Young's modulus, Poisson's ratio, Pugh's
  ratio, a ductility indicator, and specific stiffness from bulk and shear moduli.
  `elastic_frame()` returns a DataFrame shaped like `Scorecard.rank` output;
  `with_derived_properties()` returns a copy carrying the results as canonical
  properties so a `Scorecard` can rank on them. Nonphysical input (a non-positive
  modulus violates Born stability) is rejected rather than returned, since the
  negative Young's modulus it produces would rank as a legitimate candidate.
- The Materials Project connector now emits `bulk_modulus` and `shear_modulus`, and
  carries `homogeneous_poisson` and `universal_anisotropy` into `Material.metadata`.
  All four were already arriving on every fetch — the connector requests the full
  summary document — and were being discarded.
- The JARVIS connector now emits `bulk_modulus_kv` / `shear_modulus_gv` as canonical
  moduli, skipping the non-positive values it reports for unconverged tensors.
- Elastic averaging schemes are recorded in `MaterialProperty.extra`: Materials
  Project reports Voigt–Reuss–Hill, JARVIS reports Voigt, and Voigt is an upper
  bound. `Scorecard.report()` now flags any objective mixing the two under
  `mixed_averaging_schemes`.
- Three canonical property names — `youngs_modulus`, `poisson_ratio`, and
  `specific_stiffness` — plus `bulk_modulus_kv` / `shear_modulus_gv` as aliases.

### Fixed

- **The JARVIS connector returned nothing at all.** `jarvis-tools` renamed
  `Atoms.to_pymatgen` to `pymatgen_converter`, and a `hasattr` guard turned the
  missing method into a silent `None` — so every row failed to convert and
  `fetch()` returned an empty list for every query, with no error raised. The
  conversion now tries both names and raises if neither exists.
- The JARVIS connector no longer crashes on missing values. dft_3d marks them with
  the string `"na"`, which the previous NaN-only guard did not catch and which
  `float()` cannot parse.

- `Material.get_property` now canonicalizes the lookup name, so documented aliases
  resolve. Previously the write path canonicalized and the read path did not, so
  `get_numeric("k_vrh")`, `get_numeric("formation_energy")`, and
  `get_numeric("e_above_hull")` all returned `None` — and a `Scorecard` whose
  objectives used those names returned an empty shortlist with no error.
- `Scorecard` no longer lets an uninformative objective move scores. A column with
  no spread previously normalized to all-ones under `minimize` and all-zeros under
  `maximize`, so a direction label alone could change the winner on identical data;
  its weight also still entered the denominator, deflating every score. Columns that
  cannot separate candidates are now excluded from both.
- Every demo structure was a conventional cell written with an incomplete basis —
  all three `materials_sample.jsonl` records were effectively simple cubic, with
  stated densities 1.85×–3.97× what their own cells implied, and two
  `lemat_bulk_sample.json` records had the same defect. Bases are restored and every
  density is now consistent with its cell.
- Demo properties were stamped `method: "dft"` while holding room-temperature
  experimental handbook values, and elemental formation energies were nonzero, which
  is definitionally impossible. Measured values are now marked `experimental`, and
  formation energies are `0.0` with the original cohesive energies preserved under
  `extra`.
- `examples/underwater-drone-screening/shortlist_example.csv` named a winner its own
  `constraints.yaml` does not produce and ranked a candidate that config excludes. It
  is now generated by `scorecard.py` rather than hand-maintained.

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

- `scripts/ingest_oqmd.py` fetches real OQMD records through OPTIMADE. It previously
  printed "OQMD stub returned 0 materials." and exited 0.
- `Scorecard.report()`'s `mixed_averaging_schemes` now counts a property with no
  `averaging_scheme` marker as `"unspecified"` rather than skipping it. It previously
  looked only at non-null markers, so the most common dangerous case — one source
  labelling its convention and another not — left a single distinct value and was
  reported as unmixed. A pool where nothing is marked is still not flagged.
- **Breaking:** `OQMDStubConnector.fetch()` raises `NotImplementedError` instead of
  returning `[]`. An unimplemented connector answering every query with an empty
  list is indistinguishable from a real one whose filter matched nothing — the
  precise failure mode that left the JARVIS connector silently dead for an unknown
  period. Query OQMD through its OPTIMADE endpoint instead.
- **Breaking:** `mp-api` and `jarvis-tools` moved from hard dependencies of
  `mattergraph-connectors` to the `[mp]` and `[jarvis]` extras. The package already
  told users these were optional while requiring them at install time. Installing
  `mattergraph` itself is unaffected; it pulls `mattergraph-connectors[all]`.
- Connector `fetch()` takes a `ConnectorQuery`. The previous keyword form still
  works and warns; `material_ids` and `chunk_size` map to `source_ids` and
  `page_size`.
- `MaterialsProjectConnector.fetch()` honors `properties` by filtering the result,
  and raises for a property it cannot supply. It previously accepted the argument
  and discarded it, so callers had no way to tell the filter did nothing.
- `mattergraph-sim` no longer depends on `h5py`, and `mattergraph-connectors` no
  longer depends on `tqdm` or `aioitertools`; none were imported anywhere.
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
