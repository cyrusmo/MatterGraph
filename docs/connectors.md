# Connectors

| Connector | Status | Extra |
|-----------|--------|-------|
| LeMaterial bulk companion | `mattergraph_connectors.lematerial.LeMatBulk` | — |
| Materials Project | `MaterialsProjectConnector` (requires `MP_API_KEY`) | `[mp]` |
| JARVIS | `JarvisConnector` (loads a subset of JARVIS-DFT 3D) | `[jarvis]` |
| NOMAD | `NOMADConnector` (read-only public metadata; no API key for public reads) | — |
| OPTIMADE | `OptimadeConnector` — COD, OQMD, AFLOW, MP, NOMAD and ~18 more through one client | — |
| Local CSV | `load_materials_from_csv` | — |
| OQMD | No native connector; `OQMDStubConnector` **raises**. Use `OptimadeConnector(provider="oqmd")` | — |

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

## OPTIMADE

[OPTIMADE](https://www.optimade.org/) is a common API across ~20 materials databases, so one
connector reaches COD, OQMD, AFLOW, Materials Project and NOMAD without a per-source SDK.

```python
from mattergraph_connectors import ConnectorQuery, OptimadeConnector

with OptimadeConnector(provider="cod") as cod:
    materials = cod.fetch(ConnectorQuery(elements=["Ti", "O"], max_records=5))
```

| Provider | Status |
|----------|--------|
| `cod` | Verified working |
| `oqmd` | Verified working; also supplies three canonical properties (below) |
| `mp` | Listed; needs no key for OPTIMADE reads |
| `nmd` | Listed |
| `aflow` | **Down upstream.** `/v1/info` answers, but `/v1/structures` returns HTTP 500 for every query shape — including a bare request with no parameters — so there is no client-side workaround. The OPTIMADE providers dashboard reports 7/13 validator checks passing. Listed so it works when AFLOW repairs it. |

Any other OPTIMADE endpoint works via `base_url=`; the provider table is a convenience, not a
limit.

### What OPTIMADE does and does not carry

The only REQUIRED field on a structure entry is `structure_features`. The standard defines **no
physical property at all** — no band gap, formation energy, hull energy, modulus, or density.
Provider properties are namespaced (`_oqmd_stability`), so they vary per database.

That makes two things true:

- **Density is derived, not reported.** It is computed from the cell and composition and
  labelled `method="derived"` with `extra["derived_from"]`, so it is never mistaken for a value
  a source vouched for.
- **Elastic moduli never come from OPTIMADE.** Materials Project and JARVIS remain the only
  sources; after this connector their role is property enrichment rather than discovery.

### Dimensionality

Records carry `nperiodic_dimensions` into `Material.dimensionality`. **When it is not 3, no
density is derived** — a vacuum-padded monolayer's bulk density measures how much vacuum the
author added, not the material, and a `Scorecard` would otherwise rank that number against real
crystals. The structure is still kept; only the meaningless property is withheld, and the
provenance note says why.

### OQMD hull convention

`OptimadeConnector(provider="oqmd")` maps three namespaced fields onto canonical names:

| OPTIMADE field | Canonical name | Unit |
|---|---|---|
| `_oqmd_band_gap` | `band_gap` | eV |
| `_oqmd_delta_e` | `formation_energy_per_atom` | eV/atom |
| `_oqmd_stability` | `energy_above_hull` | eV/atom |

**The third is a convention mismatch, and it is recorded rather than smoothed over.** OQMD's
`stability` is a hull *distance* and goes **negative** for a phase below the current hull;
Materials Project's `energy_above_hull` is `>= 0` by construction. Ranking both in one column
biases the OQMD-sourced candidates low — the same class of error as mixing Voigt with VRH
moduli. The value is never clamped, and carries
`extra["hull_convention"] = "oqmd_hull_distance"` so a mixed column can be spotted. A constraint
like `energy_above_hull <= 0.05` will admit OQMD records that MP would have reported as `0.0`.

### Partial occupancy

COD reports `chemical_formula_reduced: null` for every partially-occupied record, because the
spec requires integer proportions and such records have formulas like `H0.572O2Ti0.858`. The
connector derives the formula from the cell it has already built instead of dropping the record.
`chemical_formula_anonymous` is never used as a fallback: `"A2B"` parses without error and would
silently write `elements=['A0+','B']`.

## Tripo3D boundary

Tripo3D is useful to track as a future concept or form-factor visualization option, but it is not a
scientific structure viewer and it is not a source of materials data, properties, provenance, or
simulation state. Public MatterGraph should prioritize connector-backed records, real structure JSON,
graph summaries, and EDA views before any generative 3D layer.
