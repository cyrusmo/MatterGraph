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

FIXTURE_RELATIVE_PATH = "data/demo/spc_real_snapshot.json"
CHGNET_REFERENCE_RELATIVE_PATH = "data/demo/chgnet_reference.json"
SOURCE_DATASET = "LeMaterial/LeMat-Bulk"
SOURCE_SUBSET = "compatible_pbe"
SLICE_NAME = "spc_tialn_candidates_v1"
TARGET = "energy_above_hull"
WORKFLOW_VERSION = "v1.0"
RUN_ID = "spc_evidence_first_snapshot_v1"
FIXTURE_DISCLAIMER = (
  "A checksummed 24-record offline snapshot of real public records. "
  "It demonstrates a reproducible workflow, not the scale of the 5.34M-row source dataset."
)
ML_BOUNDARY = (
  "CHGNet relaxation is ML-based proposal support, not a DFT or experimental measurement."
)

DEFAULT_OBJECTIVES: dict[str, dict[str, float | str]] = {
  "density": {"direction": "minimize", "weight": 0.6},
  "energy_above_hull": {"direction": "minimize", "weight": 0.4},
}
DEFAULT_CONSTRAINTS: dict[str, dict[str, float]] = {
  "energy_above_hull": {"max": 0.05},
  "max_force": {"max": 0.2},
}


def repo_root() -> Path:
  return Path(__file__).resolve().parents[4]


def fixture_path() -> Path:
  return repo_root() / FIXTURE_RELATIVE_PATH


def chgnet_reference_path() -> Path:
  return repo_root() / CHGNET_REFERENCE_RELATIVE_PATH


@lru_cache(maxsize=1)
def get_demo_artifact() -> dict[str, Any]:
  return json.loads(fixture_path().read_text())


def get_demo_manifest() -> dict[str, Any]:
  return dict(get_demo_artifact()["manifest"])


@lru_cache(maxsize=1)
def get_demo_dataset() -> MatterGraphDataset:
  artifact = get_demo_artifact()
  dataset = LeMatBulk.from_records(
    artifact["records"],
    source_dataset=SOURCE_DATASET,
    subset=SOURCE_SUBSET,
  )
  dataset.metadata["snapshot_manifest"] = artifact["manifest"]
  return dataset


def get_filtered_demo_dataset() -> MatterGraphDataset:
  return (
    get_demo_dataset()
    .filter_elements(include=["Ti", "Al", "N"])
    .filter_complexity(
      max_nsites=16,
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


def get_default_material_id() -> str:
  ranked = get_default_scorecard().rank(get_demo_store().materials)
  if ranked.empty:
    return get_demo_store().materials[0].material_id
  return str(ranked.iloc[0]["material_id"])


def graph_summary(material: Material, *, max_edges: int = 256) -> dict[str, Any]:
  if material.structure is None:
    msg = "material structure missing; graph export excluded this record"
    raise ValueError(msg)

  builder = CrystalGraphBuilder(cutoff_radius=5.0, max_neighbors=12)
  graph = builder.build(material.structure)
  edge_count = int(graph.edge_index.shape[1])
  kept_edges = min(edge_count, max(0, min(max_edges, 256)))
  edges = []
  for index in range(kept_edges):
    source = int(graph.edge_index[0, index])
    target = int(graph.edge_index[1, index])
    source_cartesian = graph.cartesian_coordinates[source]
    displacement = graph.displacement_vectors[index]
    target_cartesian = source_cartesian + displacement
    edges.append(
      {
        "source": source,
        "target": target,
        "distance": float(graph.edge_features[index, 0]),
        "image": [int(value) for value in graph.image_offsets[index].tolist()],
        "source_cartesian": [float(value) for value in source_cartesian],
        "target_cartesian": [float(value) for value in target_cartesian],
        "displacement_cartesian": [float(value) for value in displacement],
      }
    )

  all_edges = [
    (
      int(graph.edge_index[0, index]),
      int(graph.edge_index[1, index]),
      tuple(int(value) for value in graph.image_offsets[index]),
      float(graph.edge_features[index, 0]),
    )
    for index in range(edge_count)
  ]
  edge_keys = {(source, target, image) for source, target, image, _distance in all_edges}
  reciprocal = all(
    (target, source, tuple(-value for value in image)) in edge_keys
    for source, target, image, _distance in all_edges
  )
  zero_distance_count = sum(distance <= 1e-8 for *_edge, distance in all_edges)
  displacement_consistent = all(
    abs(float(graph.edge_features[index, 0]) - float(_norm(graph.displacement_vectors[index])))
    <= 1e-8
    for index in range(edge_count)
  )
  coordination_numbers = _coordination_numbers(all_edges, graph.num_atoms)
  warnings = []
  if not reciprocal:
    warnings.append("graph is not reciprocal")
  if zero_distance_count:
    warnings.append(f"{zero_distance_count} zero-distance edges")
  if graph.info["truncated_sources"]:
    warnings.append("one or more neighbor lists were truncated after a complete distance shell")
  if kept_edges < edge_count:
    warnings.append("rendering geometry is capped at 256 edges")

  return {
    "material_id": material.material_id,
    "formula": material.formula,
    "nodes": [
      {
        "index": index,
        "species": species,
        "fractional_coordinates": [float(value) for value in coords],
        "cartesian_coordinates": [
          float(value) for value in graph.cartesian_coordinates[index].tolist()
        ],
      }
      for index, (species, coords) in enumerate(
        zip(material.structure.species, material.structure.coords, strict=True)
      )
    ],
    "edges": edges,
    "edge_count": edge_count,
    "edges_truncated": kept_edges < edge_count,
    "lattice_vectors": [
      [float(value) for value in vector] for vector in graph.cell.tolist()
    ] if graph.cell is not None else [],
    "distance_shells": _distance_shells(all_edges),
    "coordination_numbers": coordination_numbers,
    "node_feature_shape": [int(value) for value in graph.node_features.shape],
    "edge_feature_shape": [int(value) for value in graph.edge_features.shape],
    "global_features": graph.global_features,
    "builder": graph.info,
    "validation": {
      "state": (
        "valid"
        if reciprocal and not zero_distance_count and displacement_consistent
        else "invalid"
      ),
      "ordered_structure": True,
      "reciprocal": reciprocal,
      "zero_distance_edges": zero_distance_count,
      "displacement_consistent": displacement_consistent,
      "complete_tied_shells": True,
      "symmetry": {
        "status": "determined" if graph.global_features["spacegroup_number"] else "unknown",
        "spacegroup_number": graph.global_features["spacegroup_number"],
      },
      "truncated": bool(graph.info["truncated_sources"]),
      "warnings": warnings,
    },
  }


def _norm(vector: Any) -> float:
  return sum(float(value) ** 2 for value in vector) ** 0.5


def _coordination_numbers(
  edges: list[tuple[int, int, tuple[int, int, int], float]],
  atom_count: int,
) -> list[int]:
  coordination: list[int] = []
  for atom in range(atom_count):
    distances = [distance for source, _target, _image, distance in edges if source == atom]
    if not distances:
      coordination.append(0)
      continue
    first = min(distances)
    coordination.append(sum(distance <= first + 0.1 for distance in distances))
  return coordination


def _distance_shells(
  edges: list[tuple[int, int, tuple[int, int, int], float]],
) -> list[dict[str, float | int]]:
  distances = sorted(distance for _source, _target, _image, distance in edges)
  shells: list[list[float]] = []
  for distance in distances:
    if not shells or distance - shells[-1][-1] > 0.1:
      shells.append([distance])
    else:
      shells[-1].append(distance)
  return [
    {
      "index": index + 1,
      "distance": sum(shell) / len(shell),
      "directed_edge_count": len(shell),
    }
    for index, shell in enumerate(shells)
  ]


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


@lru_cache(maxsize=1)
def get_chgnet_reference_artifact() -> dict[str, Any] | None:
  path = chgnet_reference_path()
  if not path.is_file():
    return None
  artifact = json.loads(path.read_text())
  artifact["scientific_boundary"] = ML_BOUNDARY
  return artifact


def chgnet_state() -> dict[str, Any]:
  reference = get_chgnet_reference_artifact()
  if reference is None:
    return {
      "state": "unavailable",
      "live_available": False,
      "reference_available": False,
      "detail": "No verified local CHGNet artifact is bundled.",
      "scientific_boundary": ML_BOUNDARY,
    }
  return {
    "state": "cached_only",
    "live_available": False,
    "reference_available": True,
    "reference_material_id": reference["material_id"],
    "model_version": reference["model"]["version"],
    "detail": "A versioned cached reference is available; live execution is not enabled.",
    "scientific_boundary": ML_BOUNDARY,
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
      "chgnet_reference",
      "CHGNet reference relaxation",
      "simulation",
      "demo_ready",
      "/simulations/chgnet/reference/{material_id}",
      boundary=ML_BOUNDARY,
    ),
    _cap(
      "ase_relax",
      "ASE/EMT smoke-test runner",
      "simulation",
      "sdk_ready",
      "/simulations/ase/relax",
      optional_dependency="ase",
      boundary="Retained for SDK smoke testing; EMT is not evidence for Ti–Al–N.",
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
