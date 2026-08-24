# Getting started

1. Clone the repository and create a virtual environment (see the root [README](https://github.com/cyrusmo/MatterGraph/blob/main/README.md)).
2. `uv sync --all-packages --group dev --extra all`
3. Run `./scripts/run_public_demo.sh` from the repository root.
4. Open `http://127.0.0.1:5173`. The launcher checks both ports, waits for API health, and stops only the processes it started.
5. Use **Guided demo** for the deterministic SPC story or **Local workbench** for a bounded CSV/JSONL file.

Use `MATTERGRAPH_API_PORT`, `MATTERGRAPH_WEB_PORT`, and `VITE_API_PROXY_TARGET` to avoid local
port collisions. `MATTERGRAPH_DEMO_DATA` remains available for a custom JSONL demo store.
`MATTERGRAPH_API_READY_TIMEOUT_SECONDS` sets the positive-integer cold-start failure ceiling
(15 seconds by default). It provides slower machines with startup headroom; it does not relax
the UI's five-second request timeout or the three-second presentation-readiness target.

**Materials Project API:** set a 32-character key in `MP_API_KEY` (preferred) or `MATERIALS_PROJECT_API_KEY` for `MaterialsProjectConnector`.
