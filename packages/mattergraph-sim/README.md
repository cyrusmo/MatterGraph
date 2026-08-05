# mattergraph-sim

Simulation job specs and runners for [MatterGraph](https://github.com/cyrusmo/MatterGraph).

Structures round-trip through pymatgen, jobs are declared as validated Pydantic specs, and runners return a structured `SimulationJob` with status, log, and result rather than raising — so a failed relaxation is data, not an exception.

## Engines

| Engine | Status |
|---|---|
| ASE | Working. Local relaxation via the EMT empirical potential (11 elements: Ag, Al, Au, C, Cu, H, N, Ni, O, Pd, Pt). |
| LAMMPS | Stub — environment-specific, returns a structured failure |
| Quantum ESPRESSO | Stub — site-specific paths and pseudopotentials, returns a structured failure |

> **Note on scope.** EMT is a fast empirical potential with narrow element coverage; it is suitable for smoke-testing a workflow end to end, not for producing quantitative results. Universal ML interatomic potentials are the intended path to periodic-table-wide coverage.

## Install

```bash
pip install mattergraph-sim
```

## Example

```python
from mattergraph_sim import AseJobSpec, SimulationJob, ase_relax

job = SimulationJob(spec=AseJobSpec(fmax=0.05, max_steps=200), input_structure=structure.model_dump())
done = ase_relax(job)
print(done.status, done.result.energy if done.result else done.error)
```

## License

Apache-2.0
