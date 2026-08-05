# mattergraph-core

Core schema, normalization, and crystal graphs for [MatterGraph](https://github.com/cyrusmo/MatterGraph) — an open-source SDK for physics-aware, provenance-aware materials workflows.

## What's in here

- **Schema** — `Material`, `MaterialProperty`, `ProvenanceRecord`, `CrystalStructure`, `SimulationJobRef`. Pydantic v2 models with strict validation (`extra="forbid"`), designed so multiple sources can report the same property without collapsing provenance.
- **Normalization** — unit conversion (energy, length, pressure, density, temperature), formula standardization, and canonical property names.
- **Crystal graphs** — `CrystalGraphBuilder` turns a pymatgen `Structure` into a periodic neighbor graph with atom and edge features. Emits plain NumPy, so there is no PyG/DGL dependency.
- **Workflow layer** — `MatterGraphDataset` and `CandidateSlice`: chainable, audited filters that produce reproducible, content-hashed candidate slices.
- **Scoring** — a deliberately transparent `Scorecard` baseline (min–max normalized objectives plus hard constraints). Not a production decision engine.

## Install

```bash
pip install mattergraph-core
```

## Example

```python
from mattergraph import MaterialStore, Scorecard

store = MaterialStore.from_demo()
scorecard = Scorecard(
    objectives={"density": "minimize", "bulk_modulus": "maximize"},
    constraints={"energy_above_hull": {"max": 0.05}},
)
print(scorecard.rank(store.materials).head())
```

## License

Apache-2.0
