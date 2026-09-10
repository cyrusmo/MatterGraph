# Constraint-to-Crystal Navigator

The navigator turns a natural-language materials request into a reviewable constraint plan and
executes only confirmed fields against a frozen public index.

```text
language → confirmation → validation → feasible set → crystal inspection → bounded recovery
```

Open `http://127.0.0.1:5173/?view=navigator` after running `./scripts/run_public_demo.sh`.

## Current public runtime

The repository works offline with the checksummed 24-record LeMat-Bulk demonstration snapshot. It
labels that surface `demo_snapshot_v1`; it does not claim to be the 25,000-record release index.
The API switches to `index_v1` only when `MATTERGRAPH_NAVIGATOR_INDEX_RAW` points to an exactly
25,000-record JSONL file built by the deterministic index tool.

```bash
uv run python scripts/build_navigator_index.py source.parquet \
  --output data/navigator/index_v1.jsonl \
  --manifest data/navigator/index_v1.manifest.json
```

The builder pins the upstream revision contract, validates PBE-compatible 3D structures,
deduplicates immutable IDs and non-null enthalpic fingerprints, allocates capacity-safe strata, and
selects each stratum using `SHA256(canonical_json([seed, immutable_id]))`.

## Scientific boundary

- Raw signed total magnetization and raw total energy are display-only.
- Net cell, per-site, and reported local magnetic moments are different executable concepts.
- “Nonmagnetic” remains unresolved until the user confirms net and local-moment semantics.
- Maximum force norm is calculation quality and is never presented as material performance.
- Energy above hull is deferred from v1.
- Missing evidence remains unknown; it is not converted into a failing number.
- Physical, calculation-quality, evidence, and capability recovery remain separate.
- Every counterfactual is relative to the named frozen index and explicitly non-causal.

The renderer accepts only a validated lattice, fractional coordinates, species/occupancies,
periodicity, units, source, method, and provenance. It displays atoms and the unit cell without
inferring chemical bonds.

## Interpreter contract

The checked-in runtime uses a bounded deterministic fallback so the public workflow remains
reproducible without model weights. The frozen Qwen3-4B contract is recorded in
`configs/navigator/model_contract.json` and remains disabled until
`scripts/smoke_navigator_model.py` passes in the exact pinned environment.

Qualification requires two clean processes. The first writes a manifest; the second must match it:

```bash
uv run python scripts/smoke_navigator_model.py --output qwen-smoke-run-1.json
uv run python scripts/smoke_navigator_model.py \
  --compare-manifest qwen-smoke-run-1.json \
  --output qwen-smoke-qualified.json
```

The smoke uses Outlines JSON-schema constrained generation and records the system prompt, output
schema, environment lock, chat template, and tokenizer-file hashes. Sampling-only arguments are
omitted from generation.

Unknown field names are rejected by the property registry even if a model proposes them.

## Benchmark and publication

`mattergraph_benchmarks.structure_intent` implements the development SFT triggers, sealed-split
overlap checks, strict public release gate, and human-request consent contract. Human-authored
requests cannot be released unless publication permission, CC BY 4.0 licensing, deidentification,
confidentiality screening, and export-control screening are all explicit.

The Docker Space publisher refuses to upload without the complete `index_v1` manifest, exactly
25,000 JSONL records, `HF_TOKEN`, and `--confirm-publish`.
