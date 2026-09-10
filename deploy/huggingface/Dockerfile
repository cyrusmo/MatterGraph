FROM node:20-slim AS web

WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MATTERGRAPH_REPO_ROOT=/app \
    MATTERGRAPH_WEB_DIST=/app/web \
    MATTERGRAPH_NAVIGATOR_INDEX_RAW=/app/data/navigator/index_v1.jsonl

WORKDIR /app
COPY packages/ ./packages/
COPY data/demo/ ./data/demo/
COPY data/navigator/ ./data/navigator/
COPY configs/navigator/ ./configs/navigator/
COPY LICENSE README.md ./
COPY --from=web /src/apps/web/dist ./web/

RUN pip install --no-cache-dir \
    ./packages/mattergraph-core \
    ./packages/mattergraph-connectors \
    ./packages/mattergraph-sim \
    ./packages/mattergraph-api

EXPOSE 7860
CMD ["uvicorn", "mattergraph_api.main:app", "--host", "0.0.0.0", "--port", "7860"]
