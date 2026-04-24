# Connectors

| Connector | Status |
|-----------|--------|
| Materials Project | `MaterialsProjectConnector` (requires `MP_API_KEY`) |
| JARVIS | `JarvisConnector` (loads a subset of JARVIS-DFT 3D) |
| Local CSV | `load_materials_from_csv` |
| OQMD / NOMAD | Stubs; extend when your workflow needs their full query surface |

Each connector should output **`Material` instances** so downstream code stays database-agnostic.
