# Roadmap (public)

- **v0.1 (current direction)** — Material schema, MP + JARVIS + local CSV, crystal graph, weighted scorecard, demo notebook, FastAPI, minimal dashboard
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
- `[connector]` Local CSV ingestion
- `[graph]` Crystal graph from pymatgen `Structure`
- `[scoring]` Weighted `Scorecard` + constraint docs
- `[api]` `/materials` and `/search`
- `[ui]` Materials table and constraint panel
- `[docs]` Getting started
- `[examples]` Template screening workflow
- `[benchmark]` Matbench adapter
- `[sim]` ASE job spec
