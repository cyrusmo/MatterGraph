# MatterGraph

[![PyPI](https://img.shields.io/pypi/v/mattergraph)](https://pypi.org/project/mattergraph/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache--2.0-green)
[![Docs](https://github.com/cyrusmo/MatterGraph/actions/workflows/docs.yml/badge.svg)](https://cyrusmo.github.io/MatterGraph/)
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
- Support **transparent baseline** scorecards with auditable ranking behavior
- Provide adapters for benchmarking and **simulation job specs** (e.g. ASE)
- Expose a **small demo API** and **minimal web UI** for end-to-end exploration
- Inspect, validate, graph, rank, and export small local CSV/JSONL datasets without uploading them

## Scope

The public repository focuses on transparent, reusable infrastructure for open materials workflows. Production-specific orchestration, hosting, and organization-specific workflows are out of scope for this demo.

MatterGraph Core focuses on transparent workflow primitives and guardrails. Proprietary ranking, active learning, orchestration, model routing, and customer-specific decision workflows remain private.

## Install

MatterGraph **0.1.0 is published on [PyPI](https://pypi.org/project/mattergraph/0.1.0/)**.
The release supports Python 3.10 and newer; its wheels, source distributions, and provenance are
also attached to the [GitHub release](https://github.com/cyrusmo/MatterGraph/releases/tag/v0.1.0).

```bash
pip install "mattergraph==0.1.0"
```

That installs the public toolkit without provider-specific SDKs. Opt into only the connector
SDKs you need:

```bash
pip install 'mattergraph[mp]==0.1.0'       # Materials Project SDK
pip install 'mattergraph[jarvis]==0.1.0'   # JARVIS SDK
pip install 'mattergraph[all]==0.1.0'      # all optional public connector SDKs
```

Install an individual package for a smaller application surface:

```bash
pip install mattergraph-core         # schema, normalization, graphs, scoring
pip install mattergraph-connectors   # NOMAD, OPTIMADE, local data, LeMat-Bulk
pip install mattergraph-sim          # ASE job specs and runners
pip install mattergraph-benchmarks   # metrics and Matbench adapter
pip install mattergraph-api          # FastAPI demo service
```

## Quickstart (from source)

```bash
git clone https://github.com/cyrusmo/MatterGraph.git
cd MatterGraph
python3 -m venv .venv
source .venv/bin/activate
pip install uv
uv sync --all-packages --group dev --extra all
# Optional: copy .env.example to .env and set MP_API_KEY for Materials Project
export MATTERGRAPH_DEMO_DATA=data/demo/materials_sample.jsonl
uv run uvicorn mattergraph_api.main:app --reload --host 0.0.0.0 --port 8000
```

For the deterministic public capability walkthrough, start the API and UI together:

```bash
./scripts/run_public_demo.sh
```

This runs a preflight-checked, checksummed snapshot of 24 real LeMaterial records at
`http://127.0.0.1:5173` without network calls or API credentials. The snapshot preserves the
upstream revision, immutable IDs, license, citation, and field-level provenance.

The UI opens in **Guided demo** mode. Choose **Local workbench** to inspect a CSV or JSONL file
up to 5 MiB / 5,000 rows. Imported datasets are ephemeral: normalized JSONL remains in memory,
the registry is capped at eight entries and 32 MiB, and only the selected dataset is
materialized. Imported content is never sent to an external service or written to disk.

Example: rank candidates with a **transparent baseline scorecard** (pool-relative min–max
objectives plus hard constraints).

```python
import json
from pathlib import Path

from mattergraph import Scorecard
from mattergraph_connectors import LeMatBulk

artifact = json.loads(Path("data/demo/spc_real_snapshot.json").read_text())
store = LeMatBulk.from_records(
    artifact["records"], subset="compatible_pbe"
).to_material_store()
scorecard = Scorecard(
    objectives={
        "density": {"direction": "minimize", "weight": 0.6},
        "energy_above_hull": {"direction": "minimize", "weight": 0.4},
    },
    constraints={
        "energy_above_hull": {"max": 0.05},
        "max_force": {"max": 0.2},
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

artifact = json.loads(Path("data/demo/spc_real_snapshot.json").read_text())
dataset = LeMatBulk.from_records(artifact["records"], subset="compatible_pbe")

candidate_slice = (
    dataset
    .filter_elements(include=["Ti", "Al", "N"])
    .filter_complexity(max_nsites=16, max_nelements=3)
    .create_slice("spc_tialn_candidates_v1", target="energy_above_hull")
)

print(candidate_slice.report())
```

## Architecture (conceptual)

```text
Raw dataset → MatterGraphDataset / Material → candidate slice / crystal graph / benchmark frame → scorecard or simulation job
```

## Roadmap

High-level [ROADMAP.md](ROADMAP.md) covers connectors, the unified schema, workflow slicing, graph building, benchmark adapters, simulation interchange, and uncertainty. For the LeMaterial companion layer, see [docs/integrations/lematerial.md](docs/integrations/lematerial.md), and for local data see [docs/local-workbench.md](docs/local-workbench.md).

## Packages

| Package | Role |
|--------|------|
| `mattergraph-core` | Schema, normalization, `MatterGraphDataset`, `CandidateSlice`, crystal graphs, transparent `Scorecard`, `MaterialStore` |
| `mattergraph-connectors` | MP, JARVIS, NOMAD public metadata, OPTIMADE, LeMat-Bulk companion adapter, bounded local CSV/JSONL import, OQMD stub |
| `mattergraph-benchmarks` | Metrics, Matbench-style adapter (optional `matbench` install) |
| `mattergraph-sim` | ASE / stub LAMMPS+QE around job specs |
| `mattergraph-api` | FastAPI demo plus ephemeral local-dataset registry, graph summaries, slicing, audited ranking, export, and labeled CHGNet reference evidence |

## License

Apache 2.0 — see [LICENSE](LICENSE).
