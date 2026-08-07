# Template screening workflow

This folder holds a **YAML scorecard** and a generated shortlist to illustrate how **transparent** multi-objective screening maps onto MatterGraph. Adapt objectives and constraints to your own engineering problem.

- `constraints.yaml` — human-readable weights and hard limits
- `scorecard.py` — loads `MaterialStore`, prints `Scorecard.report()`, applies the public `Scorecard` API
- `shortlist_example.csv` — **generated** by `scorecard.py`; do not edit by hand
- `shortlist_report.json` — the coverage and degeneracy audit for the run above

Regenerate both with:

```bash
uv run python examples/template-screening/scorecard.py
```

## What this screen actually tests

Read this before adapting the template. The screen ranks on **stiffness and mass**, and that is a narrower claim than a shortlist usually implies.

- **Bulk modulus is stiffness, not strength.** It describes resistance to uniform volumetric compression. Most structural failures are governed by something else entirely — Young's modulus and geometry for elastic buckling, yield strength for permanent deformation, fracture toughness for crack propagation — and none of those are in this screen. A ranking on `bulk_modulus` cannot tell you a part will hold.
- **`energy_above_hull ≤ 0.05` is a community convention**, not a stability threshold — roughly the Materials Project "possibly synthesizable" heuristic. It carries no kinetic information, and for elemental candidates it is close to vacuous, since an element's ground state sits at 0 by construction.
- **`density ≤ 6.0` does all the filtering here**, and it removes the highest-modulus candidate. Treat a mass limit as a project decision you are choosing to impose, not as physics the data handed you.
- **Environment is entirely outside the screen.** Nothing in the schema describes temperature, atmosphere, chemical exposure, or time. Corrosion, oxidation, fatigue, and creep are therefore structurally invisible to this ranking — for many real requirements those are the properties that actually decide the outcome.
- **Scores are pool-relative.** With only two candidates surviving the constraints, min–max normalization is binary: every objective collapses to {0, 1} and the raw magnitudes stop mattering. `shortlist_report.json` reports this as `binary_normalization: true`.

Use it as a reusable example for YAML-driven screening workflows and public demo data — and as a worked example of stating what a screen does *not* test.
