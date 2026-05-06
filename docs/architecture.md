# Architecture

MatterGraph splits concerns into importable packages:

- **Core** — `Material` / `MaterialProperty` / `CrystalStructure`, `MatterGraphDataset`, `CandidateSlice`, `MaterialStore`, `CrystalGraphBuilder`, toy `Scorecard`
- **Connectors** — fetch from public databases, emit normalized `Material` objects
- **Workflow layer** — inspect schemas, create reproducible candidate slices, export graph-ready or benchmark-ready artifacts
- **Benchmarks** — ranking metrics, training splits, optional Matbench adapter
- **Sim** — job specs and runners (e.g. ASE EMT for local relaxation in the open source)
- **API** — FastAPI + JSON, backed by a JSONL demo store

```mermaid
flowchart LR
  A[Source DB] --> B[Connector]
  B --> C["MatterGraphDataset / Material"]
  C --> D["CandidateSlice / schema report"]
  C --> E[Crystal graph]
  C --> F[Benchmark frame / scorecard]
  C --> G[Simulation job]
```

The **provenance** and **method** fields are first-class: they distinguish DFT, experiment, and model-predicted values without conflating them.

LeMaterial fits this architecture as an upstream data commons. MatterGraph stays dataset-agnostic, but the `LeMatBulk` adapter and the `MatterGraphDataset` workflow surface make it easier to inspect, slice, graph, and benchmark standardized public records without treating MatterGraph as a competing dataset host.
