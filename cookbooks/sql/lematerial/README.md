# LeMaterial SQL Cookbook

These recipes assume a DuckDB-flavored SQL environment with a table named `lemat_bulk`.

The goal is not to replace MatterGraph's Python workflow layer. The cookbook gives developers a fast way to inspect LeMaterial-style bulk records before moving into `MatterGraphDataset`, `CandidateSlice`, graph export, or benchmark preparation.

## Guardrails

- Repeated reduced formulas are **not** automatically duplicates. A formula can appear multiple times because of valid polymorphs, source overlap, or alternative structures.
- Prefer compatible subsets when joining on numerical properties.
- Preserve `immutable_id`, `structure_fingerprint`, and `functional` columns whenever the source provides them.
- Avoid comparing raw energies across unrelated formulas without additional normalization and domain checks.
