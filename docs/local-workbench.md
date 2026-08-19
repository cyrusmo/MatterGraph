# Local contributor workbench

The local workbench is a small, offline-first contribution surface alongside the deterministic
SPC walkthrough. It accepts CSV and JSONL, shows inferred mappings, validates records, and lets a
contributor inspect provenance, structures, graph readiness, slices, audited baseline rankings,
and normalized export.

## Limits and lifecycle

- CSV and JSONL only; 5 MiB and 5,000 rows maximum.
- At most 100 individual issues are returned; aggregate counts remain available.
- Strict rejection is the default. Skipping invalid rows must be explicitly selected and marks
  the dataset degraded.
- Canonical normalized JSONL bytes are kept in memory. The registry holds at most eight datasets
  and 32 MiB, evicting least-recently-used entries as needed.
- Only the selected dataset is deserialized into a `MaterialStore`.
- Imported content is not sent externally or written to disk. Reset deletes the active imported
  entry and returns to the bundled demo.

Dataset IDs are derived from the SHA-256 of canonical normalized JSONL. Export responses include
dataset ID, checksum, and record-count headers.

## CSV mapping

Map an identity column, formula, optional structure JSON, optional upstream source ID, and any
number of property columns. Each property mapping has a canonical name, optional unit, source,
and method. Unknown units are retained verbatim with a warning; mixed methods remain visible per
property.

JSONL records may already use the public `Material` shape. Each accepted row receives local-file
provenance containing only the safe basename, input checksum, and row number.

## API

The UI uses `/datasets/inspect`, `/datasets/import`, `/datasets`, dataset detail/delete/export,
and `/datasets/{id}/slices/preview`. Existing materials, search, graph-summary, audited-ranking,
and ASE smoke-test routes accept an optional `dataset_id`; omitting it always selects the bundled
demo.

The cached CHGNet AlN reference is never presented as applicable to imported data.
