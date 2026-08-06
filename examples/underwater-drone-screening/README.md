# Underwater vehicle screening (template)

This folder holds a **YAML scorecard** and a generated shortlist to illustrate how **transparent** multi-objective screening maps onto MatterGraph. Adapt objectives and constraints to your own engineering problem.

- `constraints.yaml` — human-readable weights and hard limits
- `scorecard.py` — loads `MaterialStore`, prints `Scorecard.report()`, applies the public `Scorecard` API
- `shortlist_example.csv` — **generated** by `scorecard.py`; do not edit by hand
- `shortlist_report.json` — the coverage and degeneracy audit for the run above

Regenerate both with:

```bash
uv run python examples/underwater-drone-screening/scorecard.py
```

## What this screen actually tests

Read this before adapting the template. The screen ranks on **stiffness and mass**, and the name promises more than that.

- **Bulk modulus is stiffness, not strength.** A pressure housing at depth fails by *elastic buckling of a shell*, which is governed by Young's modulus and geometry (`p_cr ∝ E(t/R)³`), not by the volumetric compression `bulk_modulus` describes. At 4000 m the hydrostatic load is ~40 MPa against moduli of order 100 GPa — three orders of magnitude apart. The real margin sits in geometry, joints, and seals, none of which a materials screen can see.
- **`energy_above_hull ≤ 0.05` is a community convention**, not a stability threshold — roughly the Materials Project "possibly synthesizable" heuristic. It carries no kinetic information, and for elemental candidates it is close to vacuous, since an element's ground state sits at 0 by construction.
- **`density ≤ 6.0` does all the filtering here**, and it removes the highest-modulus candidate. Buoyancy is a system property, not a wall-material property, so treat this limit as a project decision rather than physics.
- **Corrosion is entirely outside the screen.** Nothing in the schema describes environment. For seawater that omission is decisive — galvanic series position, chloride pitting, crevice corrosion, and stress-corrosion cracking are why deep-submergence housings are typically titanium alloys, and this ranking structurally cannot see any of it.
- **Scores are pool-relative.** With only two candidates surviving the constraints, min–max normalization is binary: every objective collapses to {0, 1} and the raw magnitudes stop mattering. `shortlist_report.json` reports this as `binary_normalization: true`.

Use it as a reusable example for YAML-driven screening workflows and public demo data — and as a worked example of stating what a screen does *not* test.
