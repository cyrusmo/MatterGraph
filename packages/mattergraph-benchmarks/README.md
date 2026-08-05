# mattergraph-benchmarks

Benchmark adapters and evaluation utilities for [MatterGraph](https://github.com/cyrusmo/MatterGraph).

## What's in here

- **Discovery metrics** — ranking-quality measures (nDCG and friends) for screening workflows, where what matters is whether good candidates surface near the top.
- **Uncertainty** — `coverage_at_target` for checking whether predicted intervals are calibrated.
- **Validation splits** — stratified splitting helpers that respect composition and structure grouping.
- **Matbench adapter** — optional bridge to [Matbench](https://matbench.materialsproject.org/) tasks. Install `matbench` separately to enable it.

## Install

```bash
pip install mattergraph-benchmarks
```

## License

Apache-2.0
