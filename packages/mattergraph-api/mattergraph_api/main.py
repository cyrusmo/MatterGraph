from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mattergraph_connectors.local_import import ImportLimitError, ImportValidationError

from mattergraph_api.routes import datasets, demo, materials, scores, search, simulations, workflows
from mattergraph_api.services.dataset_registry import (
  DatasetBusyError,
  DatasetCapacityError,
  DatasetNotFoundError,
)

app = FastAPI(
  title="MatterGraph API",
  description=(
    "Evidence-first demo API for provenanced materials records, reciprocal graph summaries, "
    "audited ranking, and explicitly labeled simulation evidence."
  ),
  version="0.1.1",
)
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

app.include_router(materials.router, tags=["materials"])
app.include_router(search.router, tags=["search"])
app.include_router(scores.router, tags=["scores"])
app.include_router(simulations.router, tags=["simulations"])
app.include_router(workflows.router, tags=["workflows"])
app.include_router(demo.router, tags=["demo"])
app.include_router(datasets.router, tags=["datasets"])


@app.exception_handler(DatasetNotFoundError)
def dataset_not_found(_request: Request, error: DatasetNotFoundError) -> JSONResponse:
  return JSONResponse(
    status_code=404,
    content={
      "detail": str(error),
      "code": "dataset_evicted" if error.evicted else "dataset_not_found",
      "dataset_id": error.dataset_id,
    },
  )


@app.exception_handler(DatasetBusyError)
def dataset_busy(_request: Request, error: DatasetBusyError) -> JSONResponse:
  return JSONResponse(status_code=409, content={"detail": str(error), "code": "dataset_busy"})


@app.exception_handler(ImportLimitError)
@app.exception_handler(DatasetCapacityError)
def dataset_limit(_request: Request, error: Exception) -> JSONResponse:
  return JSONResponse(status_code=413, content={"detail": str(error), "code": "dataset_limit"})


@app.exception_handler(ImportValidationError)
def invalid_import(_request: Request, error: ImportValidationError) -> JSONResponse:
  return JSONResponse(
    status_code=422,
    content={
      "detail": str(error),
      "code": "invalid_import",
      "report": error.report.model_dump(mode="json"),
    },
  )


@app.get("/health")
def health() -> dict[str, str]:
  return {"status": "ok"}
