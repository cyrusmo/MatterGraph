# Connectors

| Connector | Status | Extra |
|-----------|--------|-------|
| LeMaterial bulk companion | `mattergraph_connectors.lematerial.LeMatBulk` | — |
| Materials Project | `MaterialsProjectConnector` (requires `MP_API_KEY`) | `[mp]` |
| JARVIS | `JarvisConnector` (loads a subset of JARVIS-DFT 3D) | `[jarvis]` |
| NOMAD | `NOMADConnector` (read-only public metadata; no API key for public reads) | — |
| Local CSV | `load_materials_from_csv` | — |
| OQMD | Not implemented; **raises `NotImplementedError`**. Reach OQMD via OPTIMADE | — |

`mp-api` and `jarvis-tools` are optional extras, not hard dependencies:

```bash
pip install 'mattergraph-connectors[mp]'      # Materials Project
pip install 'mattergraph-connectors[jarvis]'  # JARVIS
pip install 'mattergraph-connectors[all]'     # both
```

The LeMaterial companion adapter returns a **`MatterGraphDataset`** so users can inspect schema coverage, create candidate slices, export graphs, and prepare benchmark frames before converting rows into `Material` instances. It is a dataset adapter rather than a `Connector`.

The other connectors output **`Material` instances** so downstream code stays database-agnostic.

## The connector contract

Every connector implements the `Connector` protocol and takes a single `ConnectorQuery`:

```python
from mattergraph_connectors import ConnectorQuery, NOMADConnector

with NOMADConnector() as nomad:
    materials = nomad.fetch(ConnectorQuery(elements=["Ti", "O"], max_records=5))
```

`ConnectorQuery` carries `elements`, `source_ids`, `properties`, `max_records`, and `page_size`.
The older keyword form (`fetch(elements=[...], max_records=5)`) still works and emits a
`DeprecationWarning`.

Two rules matter more than the shape:

- **A connector that cannot honor a field raises rather than ignoring it.** Asking NOMAD for
  `properties` raises, because NOMAD entries carry none; asking Materials Project for a property
  it does not map raises and names what it does supply. Silently returning everything would leave
  the caller unable to tell the filter did nothing.
- **A connector that cannot answer raises rather than returning `[]`.** `OQMDStubConnector` is
  unimplemented, so it raises. An empty list is indistinguishable from a query that legitimately
  matched nothing — which is exactly how the JARVIS connector stayed silently dead for an
  unknown period.

Every ingested `Material` now carries a `ProvenanceRecord` naming its source, upstream id, and —
where the source is specific about it — the parameters behind the numbers:

```python
material.provenance[0].source      # "jarvis"
material.provenance[0].parameters  # {"dataset": "dft_3d", "functional": "OptB88vdW"}
```

## Elastic properties and averaging schemes

Materials Project and JARVIS both supply bulk and shear moduli, and both are ingested as the
canonical `bulk_modulus` / `shear_modulus` in GPa — but **they do not report the same average**:

| Source | Upstream field | Average | Recorded as |
|--------|----------------|---------|-------------|
| Materials Project | `bulk_modulus["vrh"]`, `shear_modulus["vrh"]` | Voigt–Reuss–Hill | `extra["averaging_scheme"] = "vrh"` |
| JARVIS dft_3d | `bulk_modulus_kv`, `shear_modulus_gv` | Voigt | `extra["averaging_scheme"] = "voigt"` |

Voigt is an upper bound; VRH is not. Ranking both in one column biases the Voigt-sourced
candidates high, so `Scorecard.report()` reports any objective that mixes schemes under
`mixed_averaging_schemes`. Check it before trusting a cross-source shortlist.

Most Materials Project entries have no elastic tensor at all, so expect elastic coverage to be
sparse and read `Scorecard.report()["coverage"]` rather than assuming a full column. The MP
connector also carries `homogeneous_poisson` and `universal_anisotropy` into `Material.metadata`:
the first cross-checks the derived Poisson ratio, and the second flags records where a single
isotropic average misrepresents an anisotropic crystal.

From there, `mattergraph.derived.elastic` turns the two moduli into Young's modulus, Poisson's
ratio, a ductility indicator, and specific stiffness — see [Scoring](scoring.md).

## NOMAD public metadata

`NOMADConnector` queries NOMAD's public `entries/query` API and maps entry metadata into
MatterGraph `Material` objects. It is intentionally metadata-only in v0.1: it does not fetch NOMAD
archives, raw files, or derived scalar properties.

```python
from mattergraph_connectors import ConnectorQuery, NOMADConnector

with NOMADConnector() as nomad:
    materials = nomad.fetch(ConnectorQuery(elements=["Ti", "O"], max_records=5))

for material in materials:
    print(material.material_id, material.formula)
```

Because these entries carry no computed values, their provenance records `method="unknown"`
rather than `"dft"` — the parser name is the only hint at what produced the upload.

The connector uses public reads by default, deterministic entry-id ordering, and after-value
pagination. Public NOMAD metadata reads do not require an API key.

## Tripo3D boundary

Tripo3D is useful to track as a future concept or form-factor visualization option, but it is not a
scientific structure viewer and it is not a source of materials data, properties, provenance, or
simulation state. Public MatterGraph should prioritize connector-backed records, real structure JSON,
graph summaries, and EDA views before any generative 3D layer.
