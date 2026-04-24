from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import materials, scores, search, simulations

app = FastAPI(
  title="MatterGraph API",
  description="Open demo API for materials records, search, basic ranking, and ASE hooks.",
  version="0.1.0",
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


@app.get("/health")
def health() -> dict[str, str]:
  return {"status": "ok"}
