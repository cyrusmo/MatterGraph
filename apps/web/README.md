# MatterGraph web (demo)

Vite + React + TypeScript. The presentation-safe path starts the deterministic API fixture,
waits for its preflight checks, and then starts Vite:

```bash
./scripts/run_public_demo.sh
```

The UI is available at `http://127.0.0.1:5173`. The launcher defaults the API to port `8001`,
fails without stopping anything if either port is occupied, and cleans up only its own child
process. Override ports with `MATTERGRAPH_API_PORT` and `MATTERGRAPH_WEB_PORT`.

For separate development shells, the Vite server proxies API paths to
`VITE_API_PROXY_TARGET` (default `http://127.0.0.1:8001`).

```bash
cd apps/web
npm install
npm run dev
```

Start the API from the monorepo root in another shell:

```bash
uv run uvicorn mattergraph_api.main:app --reload --port 8001
```

`VITE_API_PROXY_TARGET` controls the development proxy only. `VITE_API_URL` stays empty for
same-origin proxying, or can be set to a full base URL in production.

## Production build

```bash
npm run build
# static files in dist/ — serve with nginx, Firebase Hosting, S3+CloudFront, etc.
```
