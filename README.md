# MatterGraph

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
![CI](https://github.com/cyrusmo/MatterGraph/actions/workflows/ci.yml/badge.svg)
![Status](https://img.shields.io/badge/status-alpha-orange)

Open-source **materials data infrastructure** for physics-aware machine learning and simulation workflows.

MatterGraph helps researchers and engineers **ingest, normalize, search, compare, and benchmark** materials data from public sources such as [Materials Project](https://materialsproject.org), [OQMD](https://oqmd.org), [JARVIS](https://jarvis.nist.gov), and [NOMAD](https://nomad-lab.eu).

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

## Architecture (conceptual)

```text
Raw dataset → normalized Material → crystal graph / features → scorecard or benchmarks → simulation job
```

## Roadmap

High-level [ROADMAP.md](ROADMAP.md) covers connectors, the unified schema, graph building, benchmark adapters, simulation job specs, and uncertainty. Open issues label components as `[core]`, `[connector]`, `[graph]`, and so on.

## Packages

| Package | Role |
|--------|------|
| `mattergraph-core` | Schema, normalization, crystal graphs, toy `Scorecard`, `MaterialStore` |
| `mattergraph-connectors` | MP, JARVIS, local CSV, stubs for NOMAD/OQMD |
| `mattergraph-benchmarks` | Metrics, Matbench-style adapter (optional `matbench` install) |
| `mattergraph-sim` | ASE / stub LAMMPS+QE around job specs |
| `mattergraph-api` | FastAPI demo for `/materials`, `/search`, `/scores/rank`, `/simulations/ase/relax` |

## License

Apache 2.0 — see [LICENSE](LICENSE).
