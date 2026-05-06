# Roadmap (public)

- **v0.1 (current direction)** — Material schema, MP + JARVIS + local CSV, LeMat-Bulk workflow companion, `MatterGraphDataset`, `CandidateSlice`, crystal graph, weighted scorecard, demo notebook, FastAPI, minimal dashboard
- **Workflow layer** — richer `CandidateSlice.report()` output, benchmark-frame presets, more transparent filtering recipes, offline-first analysis helpers
- **LeMaterial companion** — deepen `LeMat-Bulk` coverage, document `LeMat-Traj` / `LeMat-Synth` as future integrations, expand the SQL/EDA cookbook
- **Connectors** — NOMAD and OQMD beyond thin stubs, with stable pagination and error handling
- **Schema** — Richer `ProvenanceRecord` and simulation linkage across databases
- **Graphs** — More edge/node features, optional DGL/PyG examples while keeping the core library lightweight
- **Benchmarks** — Tighter Matbench / leaderboard examples
- **Simulation** — Documented LAMMPS/QE images and parsers for common outputs
- **Uncertainty** — First-class epistemic/aleatory fields where sources provide them

## Seed issues (suggested on GitHub)

- `[core]` Define and freeze `Material` + `MaterialProperty` + provenance
- `[connector]` Materials Project connector
- `[connector]` JARVIS connector
- `[connector]` LeMat-Bulk adapter
- `[connector]` Local CSV ingestion
- `[workflow]` Reproducible `CandidateSlice` reporting
- `[workflow]` Graph-ready and benchmark-ready dataset exports
- `[graph]` Crystal graph from pymatgen `Structure`
- `[scoring]` Weighted `Scorecard` + constraint docs
- `[api]` `/materials` and `/search`
- `[ui]` Materials table and constraint panel
- `[docs]` Getting started
- `[docs]` LeMaterial integration guide
- `[examples]` Template screening workflow
- `[cookbook]` LeMaterial SQL / EDA recipes
- `[benchmark]` Matbench adapter
- `[sim]` ASE job spec
