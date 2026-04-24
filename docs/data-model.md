# Data model

The central object is **`Material`**: formula, elements, optional `CrystalStructure`, a list of **`MaterialProperty`** entries, and **`ProvenanceRecord`** for lineage.

Properties carry `source`, `method` (`dft`, `experimental`, `model_predicted`, `unknown`), and optional `confidence` / `uncertainty` when the upstream provides them.

JSON interchange shapes live under `data/schemas/` and mirror the Pydantic models in `mattergraph-core`.
