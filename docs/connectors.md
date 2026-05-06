# Connectors

| Connector | Status |
|-----------|--------|
| LeMaterial bulk companion | `mattergraph_connectors.lematerial.LeMatBulk` |
| Materials Project | `MaterialsProjectConnector` (requires `MP_API_KEY`) |
| JARVIS | `JarvisConnector` (loads a subset of JARVIS-DFT 3D) |
| Local CSV | `load_materials_from_csv` |
| OQMD / NOMAD | Stubs; extend when your workflow needs their full query surface |

The LeMaterial companion adapter returns a **`MatterGraphDataset`** so users can inspect schema coverage, create candidate slices, export graphs, and prepare benchmark frames before converting rows into `Material` instances.

The other connectors currently output **`Material` instances** so downstream code stays database-agnostic.
