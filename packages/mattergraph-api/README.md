# mattergraph-api

FastAPI demo service for [MatterGraph](https://github.com/cyrusmo/MatterGraph).

This is a **demonstration surface**, not a production service: storage is an in-memory store loaded from a JSONL fixture, and the persistence layer under `mattergraph_api/db/` is a placeholder for installations that need one.

## Routes

| Route | Purpose |
|---|---|
| `GET /health` | Liveness |
| `GET /materials`, `GET /materials/{mid}` | Browse normalized records |
| `GET /search?element=` | Filter by element |
| `POST /scores/rank` | Rank candidates with objectives, constraints, and weights |
| `POST /simulations/ase/relax` | Run an ASE relaxation (503 if `ase` is unavailable) |
| `GET /workflows/lematerial/demo` | End-to-end LeMat-Bulk screening walkthrough |

## Install and run

```bash
pip install mattergraph-api
uvicorn mattergraph_api.main:app --host 0.0.0.0 --port 8000
```

The default API uses the packaged, checksummed 24-record LeMaterial example. Set
`MATTERGRAPH_DEMO_DATA` only when intentionally replacing it with a custom JSONL store.

## License

Apache-2.0
