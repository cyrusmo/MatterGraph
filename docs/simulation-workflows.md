# Simulation workflows

The `mattergraph-sim` package defines **`SimulationJob`** and `AseJobSpec`. The reference implementation uses **ASE** with the EMT calculator for local relaxation and returns structured result metadata including convergence, energy, forces, and the relaxed structure. Unsupported species fail as structured jobs instead of uncaught exceptions. **LAMMPS** and **Quantum ESPRESSO** entry points are **stubs** that document how to wire binaries and inputs in a site-specific or HPC environment.

The FastAPI route `POST /simulations/ase/relax` runs a small relaxation for a material that already has a `structure` in the demo store.

`SimulationResultEnvelope` is the public interchange type for importing an external result. It
records engine/version, method, parameters, input/output checksums, convergence, properties,
artifacts, and provenance. It does not launch or coordinate simulators.

```python
from mattergraph import SimulationResultEnvelope

result = SimulationResultEnvelope(
    engine="lammps",
    engine_version="stable_29Aug2024",
    method="external result import",
    parameters={"units": "metal"},
    input_checksum_sha256="a" * 64,
    output_checksum_sha256="b" * 64,
    converged=True,
)
```

The cached CHGNet artifact is evidence for bundled material `agm003273599` only. The local
workbench never applies it to imported data. Every CHGNet result carries this boundary:
**CHGNet relaxation is ML-based proposal support, not a DFT or experimental measurement.**
