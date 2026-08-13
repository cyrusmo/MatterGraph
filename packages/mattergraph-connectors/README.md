# mattergraph-connectors

Connectors to public materials databases for [MatterGraph](https://github.com/cyrusmo/MatterGraph).

Each connector returns normalized `Material` records from `mattergraph-core`, so downstream filtering, graph export, and scoring work identically regardless of source.

## Sources

| Connector | Status |
|---|---|
| Materials Project (`mp-api`) | Supported — requires `MP_API_KEY` |
| JARVIS-DFT (`jarvis-tools`) | Supported |
| NOMAD | Public metadata reads, no API key needed. Metadata-only in v0.1 — does not fetch archives or derived scalar properties. |
| LeMat-Bulk | Companion adapter (records, parquet, or Hugging Face `datasets`) |
| Local CSV | Supported |
| OQMD | Stub — preserves the API surface, returns no records |

Heavy source SDKs are imported lazily, so importing the package stays cheap and a missing optional dependency produces a readable install hint rather than an `ImportError` traceback.

## Install

```bash
pip install mattergraph-connectors
```

## Example

```python
import json
from pathlib import Path

from mattergraph_connectors import LeMatBulk

artifact = json.loads(Path("data/demo/spc_real_snapshot.json").read_text())
dataset = LeMatBulk.from_records(artifact["records"], subset="compatible_pbe")

candidates = (
    dataset
    .filter_elements(include=["Ti", "Al", "N"])
    .filter_complexity(max_nsites=16, max_nelements=3)
    .create_slice("spc_tialn_candidates_v1", target="energy_above_hull")
)
print(candidates.report())
```

## License

Apache-2.0
