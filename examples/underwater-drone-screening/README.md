# Underwater vehicle screening (template)

This folder holds a **YAML scorecard** and a tiny CSV shortlist to illustrate how **transparent** multi-objective screening maps onto MatterGraph. It is **not** a mission-specific or classified workflow — adapt objectives and constraints to your own engineering problem.

- `constraints.yaml` — human-readable weights and hard limits
- `scorecard.py` — loads `MaterialStore` and applies the public `Scorecard` API
- `shortlist_example.csv` — example tabular view

The **real** “mission-aware optimization engine” belongs in a private product repository alongside proprietary data and schedulers.
