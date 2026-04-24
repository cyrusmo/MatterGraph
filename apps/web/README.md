# MatterGraph web (demo)

Vite + React + TypeScript. In development, the dev server **proxies** API paths to `http://127.0.0.1:8000` (see `vite.config.ts`).

```bash
cd apps/web
npm install
npm run dev
```

Start the API from the monorepo root in another shell:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

`VITE_API_URL` can be set to an empty string for the proxy, or a full base URL in production (and adjust CORS on the API).

## Production build

```bash
npm run build
# static files in dist/ — serve with nginx, Firebase Hosting, S3+CloudFront, etc.
```
