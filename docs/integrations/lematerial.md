# Using MatterGraph with LeMaterial

## Relationship

LeMaterial is an upstream materials data commons.

MatterGraph is a downstream workflow surface.

LeMaterial standardizes and distributes public materials datasets. MatterGraph helps developers inspect those records, apply transparent filters, create reproducible candidate slices, export crystal graphs, and prepare benchmark-ready frames.

## What MatterGraph adds

- schema inspection and coverage reports
- candidate slicing with deterministic `slice_id` values
- guardrails around mixed functionals and duplicate-sensitive slices
- graph export with explicit missing-structure accounting
- benchmark-frame creation for downstream model training and evaluation
- SQL / EDA cookbook assets for offline-first analysis

## What MatterGraph does not do

- rehost LeMaterial
- replace LeMaterial schemas
- claim ownership of LeMaterial datasets
- provide proprietary ranking inside the open-source core

## Example workflow

```text
LeMat-Bulk -> MatterGraphDataset -> CandidateSlice -> Graphs -> Benchmark frame
```

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

graphs = dataset.to_graphs()
benchmark_frame = dataset.to_benchmark_frame(target="bulk_modulus")

print(candidate_slice.report())
print(graphs.excluded_count)
print(benchmark_frame[["material_id", "target"]].head())
```

## Guardrail notes

- Repeated reduced formulas are not automatically treated as duplicates. Different structures and valid polymorphs can share the same formula.
- Duplicate-sensitive guardrails focus on exact repeated records, immutable-id collisions, or structure-fingerprint collisions.
- `formula_only` deduplication is available only as an explicit opt-in mode.

## Related assets

- [`examples/lematerial/`](../../examples/lematerial/)
- [`cookbooks/sql/lematerial/`](../../cookbooks/sql/lematerial/)
