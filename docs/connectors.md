# Connectors

| Connector | Status |
|-----------|--------|
| LeMaterial bulk companion | `mattergraph_connectors.lematerial.LeMatBulk` |
| Materials Project | `MaterialsProjectConnector` (requires `MP_API_KEY`) |
| JARVIS | `JarvisConnector` (loads a subset of JARVIS-DFT 3D) |
| NOMAD | `NOMADConnector` (read-only public metadata; no API key for public reads) |
| Local CSV | `load_materials_from_csv` |
| OQMD | Stub; extend when your workflow needs its full query surface |

The LeMaterial companion adapter returns a **`MatterGraphDataset`** so users can inspect schema coverage, create candidate slices, export graphs, and prepare benchmark frames before converting rows into `Material` instances.

The other connectors currently output **`Material` instances** so downstream code stays database-agnostic.

## NOMAD public metadata

`NOMADConnector` queries NOMAD's public `entries/query` API and maps entry metadata into
MatterGraph `Material` objects. It is intentionally metadata-only in v0.1: it does not fetch NOMAD
archives, raw files, or derived scalar properties.

```python
from mattergraph_connectors import NOMADConnector

with NOMADConnector() as nomad:
    materials = nomad.fetch(elements=["Ti", "O"], max_records=5)

for material in materials:
    print(material.material_id, material.formula)
```

The connector uses public reads by default, deterministic entry-id ordering, and after-value
pagination. Public NOMAD metadata reads do not require an API key.

## Tripo3D boundary

Tripo3D is useful to track as a future concept or form-factor visualization option, but it is not a
scientific structure viewer and it is not a source of materials data, properties, provenance, or
simulation state. Public MatterGraph should prioritize connector-backed records, real structure JSON,
graph summaries, and EDA views before any generative 3D layer.
