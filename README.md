# MatterGraph

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![CI](https://github.com/cyrusmo/MatterGraph/actions/workflows/ci.yml/badge.svg)
![Status](https://img.shields.io/badge/status-alpha-orange)

MatterGraph is an open-source SDK and workbench for physics-aware materials workflows.

It helps researchers and developers turn standardized materials datasets into graph-ready, benchmark-ready, and candidate-screening artifacts. MatterGraph is dataset-agnostic and supports multi-source workflows across public materials resources.

LeMaterial is a flagship upstream companion: LeMaterial provides standardized materials datasets; MatterGraph provides the downstream workflow surface for inspection, filtering, graph export, slicing, and evaluation.

It is designed for teams building:

- materials screening and comparison tools
- graph-based materials ML models
- simulation-backed discovery workflows
- uncertainty-aware engineering decision support

MatterGraph is **not** a black-box “AI materials scientist.” It is **infrastructure** for transparent, physics-aware materials workflows.

## Why MatterGraph?

Materials data is fragmented across repositories, schemas, units, structures, and property definitions. MatterGraph provides a **common, provenance-aware layer** for turning raw materials records into normalized, ML-ready, simulation-aware material objects.

## What it does

- Ingest public materials datasets
- Normalize formulas, structures, units, and properties
- Convert crystal structures into **crystal graph** representations
- Track property provenance and basic confidence
- Support **toy** scorecards and ranking (transparent baselines)
- Provide adapters for benchmarking and **simulation job specs** (e.g. ASE)
- Expose a **small demo API** and **minimal web UI** for end-to-end exploration

## Scope

The public repository focuses on transparent, reusable infrastructure for open materials workflows. Production-specific orchestration, hosting, and organization-specific workflows are out of scope for this demo.

MatterGraph Core focuses on transparent workflow primitives and guardrails. Proprietary ranking, active learning, orchestration, model routing, and customer-specific decision workflows remain private.

## Quickstart

```bash
git clone https://github.com/cyrusmo/MatterGraph.git
cd MatterGraph
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync --all-packages --group dev
# Optional: copy .env.example to .env and set MP_API_KEY for Materials Project
export MATTERGRAPH_DEMO_DATA=data/demo/materials_sample.jsonl
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Example: rank candidates with a **toy scorecard** (min–max normalized objectives, hard constraints).

```python
from mattergraph import MaterialStore, Scorecard

store = MaterialStore.from_demo()
scorecard = Scorecard(
    objectives={
        "density": "minimize",
        "bulk_modulus": "maximize",
    },
    constraints={
        "energy_above_hull": {"max": 0.05},
        "density": {"max": 6.0},
    },
)
df = scorecard.rank(store.materials)
print(df.head(10))
```

Example: turn LeMaterial-style records into a reproducible candidate slice.

```python
import json
from pathlib import Path

from mattergraph_connectors import LeMatBulk

records = json.loads(Path("data/demo/lemat_bulk_sample.json").read_text())
dataset = LeMatBulk.from_records(records, subset="compatible_pbesol")

candidate_slice = (
    dataset
    .filter_elements(include=["Ti", "Al", "N"])
    .filter_complexity(max_nsites=4, max_nelements=3)
    .create_slice("marine_pressure_candidates_v0", target="bulk_modulus")
)

print(candidate_slice.report())
```

## Architecture (conceptual)

```text
Raw dataset → MatterGraphDataset / Material → candidate slice / crystal graph / benchmark frame → scorecard or simulation job
```

## Roadmap

High-level [ROADMAP.md](ROADMAP.md) covers connectors, the unified schema, workflow slicing, graph building, benchmark adapters, simulation job specs, and uncertainty. For the LeMaterial companion layer, see [docs/integrations/lematerial.md](docs/integrations/lematerial.md).

## Packages

| Package | Role |
|--------|------|
| `mattergraph-core` | Schema, normalization, `MatterGraphDataset`, `CandidateSlice`, crystal graphs, toy `Scorecard`, `MaterialStore` |
| `mattergraph-connectors` | MP, JARVIS, LeMat-Bulk companion adapter, local CSV, stubs for NOMAD/OQMD |
| `mattergraph-benchmarks` | Metrics, Matbench-style adapter (optional `matbench` install) |
| `mattergraph-sim` | ASE / stub LAMMPS+QE around job specs |
| `mattergraph-api` | FastAPI demo for `/materials`, `/search`, `/scores/rank`, `/simulations/ase/relax` |

## License

Apache 2.0 — see [LICENSE](LICENSE).
