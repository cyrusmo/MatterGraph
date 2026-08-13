from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from mattergraph import Material, MaterialStore, Scorecard
from mattergraph.datasets import MatterGraphDataset
from mattergraph.graph import CrystalGraphBuilder
from mattergraph_connectors import LeMatBulk
from mattergraph_sim.ase_runner import EMT_SUPPORTED_SPECIES

FIXTURE_RELATIVE_PATH = "data/demo/lemat_bulk_sample.json"
SOURCE_DATASET = "LeMaterial/LeMat-Bulk"
SOURCE_SUBSET = "compatible_pbesol"
SLICE_NAME = "bulk_modulus_candidates_v0"
TARGET = "bulk_modulus"
DEFAULT_MATERIAL_ID = "lemat-aln"
WORKFLOW_VERSION = "v0.2"
RUN_ID = "lematerial_bulk_demo_static_v0_2"
FIXTURE_DISCLAIMER = (
  "Illustrative bundled records shaped like LeMaterial bulk data. "
  "They demonstrate workflow behavior, not dataset scale or production predictions."
)

DEFAULT_OBJECTIVES: dict[str, dict[str, float | str]] = {
  "density": {"direction": "minimize", "weight": 0.6},
  "bulk_modulus": {"direction": "maximize", "weight": 0.4},
}
DEFAULT_CONSTRAINTS: dict[str, dict[str, float]] = {
  "energy_above_hull": {"max": 0.025},
  "density": {"max": 6.0},
}


def repo_root() -> Path:
  return Path(__file__).resolve().parents[4]


def fixture_path() -> Path:
  return repo_root() / FIXTURE_RELATIVE_PATH


@lru_cache(maxsize=1)
def get_demo_dataset() -> MatterGraphDataset:
  records = json.loads(fixture_path().read_text())
  return LeMatBulk.from_records(
    records,
    source_dataset=SOURCE_DATASET,
    subset=SOURCE_SUBSET,
  )


def get_filtered_demo_dataset() -> MatterGraphDataset:
  return (
    get_demo_dataset()
    .filter_elements(include=["Ti", "Al", "N"])
    .filter_complexity(
      max_nsites=4,
      max_nelements=3,
    )
  )


@lru_cache(maxsize=1)
def get_demo_store() -> MaterialStore:
  return get_demo_dataset().to_material_store()


def get_default_scorecard() -> Scorecard:
  return Scorecard(
    objectives=DEFAULT_OBJECTIVES,  # type: ignore[arg-type]
    constraints=DEFAULT_CONSTRAINTS,
  )


def graph_summary(material: Material, *, max_edges: int = 96) -> dict[str, Any]:
  if material.structure is None:
    msg = "material structure missing; graph export excluded this record"
    raise ValueError(msg)

  builder = CrystalGraphBuilder()
  graph = builder.build(material.structure)
  edge_count = int(graph.edge_index.shape[1])
  kept_edges = min(edge_count, max_edges)
  edges = []
  for index in range(kept_edges):
    edges.append(
      {
        "source": int(graph.edge_index[0, index]),
        "target": int(graph.edge_index[1, index]),
        "distance": float(graph.edge_features[index, 0]),
        "image": [int(value) for value in graph.image_offsets[index].tolist()],
      }
    )

  return {
    "material_id": material.material_id,
    "formula": material.formula,
    "nodes": [
      {
        "index": index,
        "species": species,
        "fractional_coordinates": [float(value) for value in coords],
      }
      for index, (species, coords) in enumerate(
        zip(material.structure.species, material.structure.coords, strict=True)
      )
    ],
    "edges": edges,
    "edge_count": edge_count,
    "edges_truncated": kept_edges < edge_count,
    "node_feature_shape": [int(value) for value in graph.node_features.shape],
    "edge_feature_shape": [int(value) for value in graph.edge_features.shape],
    "global_features": graph.global_features,
    "builder": graph.info,
  }


def simulation_readiness(material: Material) -> dict[str, Any]:
  ase_available = importlib.util.find_spec("ase") is not None
  unsupported = sorted(set(material.elements) - set(EMT_SUPPORTED_SPECIES))
  structure_present = material.structure is not None
  ready = ase_available and structure_present and not unsupported
  if not ase_available:
    reason = "ASE is not installed in this environment."
  elif not structure_present:
    reason = "No crystal structure is available for relaxation."
  elif unsupported:
    reason = f"EMT does not support: {', '.join(unsupported)}."
  else:
    reason = "ASE/EMT supports every species in this structure."
  return {
    "ready": ready,
    "ase_available": ase_available,
    "calculator": "emt",
    "unsupported_species": unsupported,
    "reason": reason,
  }


def capability_catalog() -> list[dict[str, Any]]:
  return [
    _cap(
      "lematerial",
      "LeMaterial adapter",
      "workflow",
      "demo_ready",
      "/workflows/lematerial/demo",
    ),
    _cap(
      "candidate_slices",
      "Candidate slicing + guardrails",
      "workflow",
      "demo_ready",
      "CandidateSlice.report",
    ),
    _cap(
      "crystal_graphs",
      "Crystal graph export",
      "graphs",
      "demo_ready",
      "/materials/{id}/graph-summary",
    ),
    _cap(
      "benchmark_frames",
      "Benchmark-ready frames",
      "benchmarks",
      "demo_ready",
      "MatterGraphDataset.to_benchmark_frame",
    ),
    _cap(
      "scorecard_audit",
      "Transparent scorecard audit",
      "ranking",
      "demo_ready",
      "/scores/rank/audit",
    ),
    _cap(
      "ase_relax",
      "ASE local relaxation",
      "simulation",
      "demo_ready",
      "/simulations/ase/relax",
      optional_dependency="ase",
    ),
    _cap(
      "materials_project",
      "Materials Project",
      "connectors",
      "sdk_ready",
      "MaterialsProjectConnector",
      optional_dependency="mp-api",
    ),
    _cap(
      "jarvis",
      "JARVIS-DFT",
      "connectors",
      "sdk_ready",
      "JarvisConnector",
      optional_dependency="jarvis-tools",
    ),
    _cap("nomad", "NOMAD public metadata", "connectors", "sdk_ready", "NOMADConnector"),
    _cap("optimade", "OPTIMADE / OQMD", "connectors", "sdk_ready", "OptimadeConnector"),
    _cap("local_csv", "Local CSV", "connectors", "sdk_ready", "load_materials_from_csv"),
    _cap(
      "elastic", "Derived elasticity", "derived", "sdk_ready", "mattergraph.derived.elastic"
    ),
    _cap(
      "benchmark_utilities",
      "Metrics, splits + uncertainty",
      "benchmarks",
      "sdk_ready",
      "mattergraph-benchmarks",
      optional_dependency="scikit-learn / matbench",
    ),
    _cap(
      "oqmd_native",
      "Native OQMD connector",
      "connectors",
      "stub",
      "OQMDStubConnector",
      boundary="Use the working OPTIMADE OQMD provider instead.",
    ),
    _cap("lammps", "LAMMPS runner", "simulation", "stub", "run_lammps"),
    _cap(
      "quantum_espresso",
      "Quantum ESPRESSO runner",
      "simulation",
      "stub",
      "run_quantum_espresso",
    ),
    _cap(
      "persistence",
      "Persistent workflow database",
      "platform",
      "out_of_scope",
      "open-source demo uses an in-memory store",
    ),
    _cap(
      "production_ranking",
      "Production ranking + orchestration",
      "platform",
      "out_of_scope",
      "not part of the public baseline",
    ),
    _cap(
      "active_learning",
      "Active-learning operations",
      "platform",
      "out_of_scope",
      "not part of the public baseline",
    ),
  ]


def _cap(
  capability_id: str,
  label: str,
  category: str,
  status: str,
  evidence: str,
  *,
  optional_dependency: str | None = None,
  boundary: str | None = None,
) -> dict[str, Any]:
  return {
    "id": capability_id,
    "label": label,
    "category": category,
    "status": status,
    "evidence": evidence,
    "optional_dependency": optional_dependency,
    "boundary": boundary,
  }
