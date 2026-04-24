# Simulation workflows

The `mattergraph-sim` package defines **`SimulationJob`** and `AseJobSpec`. The reference implementation uses **ASE** with a simple calculator (e.g. EMT) for local relaxation. **LAMMPS** and **Quantum ESPRESSO** entry points are **stubs** that document how to wire binaries and inputs in a site-specific or HPC environment.

The FastAPI route `POST /simulations/ase/relax` runs a small relaxation for a material that already has a `structure` in the demo store.
