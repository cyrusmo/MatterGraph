# Underwater vehicle screening (template)

This folder holds a **YAML scorecard** and a tiny CSV shortlist to illustrate how **transparent** multi-objective screening maps onto MatterGraph. Adapt objectives and constraints to your own engineering problem.

- `constraints.yaml` — human-readable weights and hard limits
- `scorecard.py` — loads `MaterialStore` and applies the public `Scorecard` API
- `shortlist_example.csv` — example tabular view

Use it as a reusable example for YAML-driven screening workflows and public demo data.
