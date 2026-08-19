# Data model

The central object is **`Material`**: formula, elements, optional `CrystalStructure`, a list of **`MaterialProperty`** entries, and **`ProvenanceRecord`** for lineage. Existing `0.1` JSON records remain valid.

Properties carry `source`, `method` (`dft`, `experimental`, `model_predicted`, `derived`, `unknown`), and optional `confidence` / `uncertainty` when the upstream provides them.

Optional **`PropertyContext`** records decision-neutral conditions: temperature, pressure,
environment, orientation, material state, process route, specimen, test method, instrument,
statistical basis, and applicability. **`SourceArtifact`** carries citation/DOI, URI, upstream
revision, page, license, and SHA-256 integrity metadata. These fields describe evidence; they do
not encode approval, requirements, qualification, or decision linkage.

**`DatasetManifest`** gives a normalized dataset a deterministic content identity and records
source format, accepted/rejected counts, degradation state, content and normalized checksums,
and normalized byte size. **`SimulationResultEnvelope`** is the corresponding engine-neutral
evidence contract for imported results.

```python
from mattergraph import MaterialProperty, PropertyContext, Quantity, SourceArtifact

value = MaterialProperty(
    name="yield_strength",
    value=410,
    unit="MPa",
    source="published_table",
    method="experimental",
    context=PropertyContext(
        temperature=Quantity(value=298.15, unit="K"),
        orientation="rolling direction",
        test_method="ASTM E8",
    ),
    source_artifact=SourceArtifact(
        citation="Example et al. (2025)",
        license="CC-BY-4.0",
        checksum_sha256="a" * 64,
    ),
)
```

Pydantic models are the source of truth for JSON interchange. Canonically formatted schemas live
under `data/schemas/`; regenerate with `python scripts/generate_schemas.py` and verify drift with
`python scripts/generate_schemas.py --check`.
