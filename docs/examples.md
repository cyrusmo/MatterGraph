# Examples

See the [`examples/`](https://github.com/cyrusmo/MatterGraph/tree/main/examples/) directory: ingest scripts, normalization, building crystal graphs, ranking, and an ASE relaxation script.

For the new workflow companion layer, the [`examples/lematerial/`](https://github.com/cyrusmo/MatterGraph/tree/main/examples/lematerial/) folder shows:

- schema inspection with `MatterGraphDataset.schema_report()`
- reproducible candidate slicing with `CandidateSlice.report()`
- graph export with missing-structure accounting

The [`cookbooks/sql/lematerial/`](https://github.com/cyrusmo/MatterGraph/tree/main/cookbooks/sql/lematerial/) folder complements those examples with DuckDB-flavored SQL / EDA recipes for working with LeMaterial-style bulk tables.

The `template-screening` folder remains a **template** for YAML-driven objectives and a toy score path, not a productized workflow.

For interactive work, add Jupyter where your environment allows. The repository stays lightweight and CI-friendly with runnable `.py` examples first.
