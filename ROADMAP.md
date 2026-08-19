# Roadmap (public)

- **v0.1 (implemented public foundation)** — additive contextual Material schema, generated JSON Schemas, MP/JARVIS/NOMAD/OPTIMADE plus bounded local CSV/JSONL import, LeMat-Bulk workflow companion, periodic crystal graph, transparent scorecard, ephemeral FastAPI registry, guided demo and local contributor workbench
- **Workflow layer** — richer `CandidateSlice.report()` output, benchmark-frame presets, more transparent filtering recipes, offline-first analysis helpers
- **LeMaterial companion** — deepen `LeMat-Bulk` coverage, document `LeMat-Traj` / `LeMat-Synth` as future integrations, expand the SQL/EDA cookbook
- **Connectors** — deepen native provider coverage while reusing bounded timeout/retry/`Retry-After` policy; OQMD remains available through OPTIMADE and native OQMD remains an explicit stub
- **Schema** — evolve additively from Pydantic source models; preserve contextual properties, dataset manifests, source artifacts and simulation-result envelopes
- **Graphs** — More edge/node features, optional DGL/PyG examples while keeping the core library lightweight
- **Benchmarks** — Tighter Matbench / leaderboard examples
- **Simulation** — result-import/parser examples around `SimulationResultEnvelope`; LAMMPS/QE execution and multi-simulator orchestration remain out of scope
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
