#!/usr/bin/env python3
"""Generate the checked-in CHGNet reference for the deterministic demo leader.

This maintainer command requires CHGNet and torch, but the public demo does not. The artifact
records both the runtime package and the pretrained model version so those are never conflated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chgnet
from chgnet.model import CHGNet, StructOptimizer
from mattergraph_api.services.demo_service import get_default_material_id, get_demo_store

MODEL_NAME = "0.3.0"
FMAX = 0.1
MAX_STEPS = 50


def _canonical_hash(value: Any) -> str:
  payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
  return hashlib.sha256(payload).hexdigest()


def _weight_path() -> Path:
  import chgnet as package

  return (
    Path(package.__file__).resolve().parent
    / "pretrained"
    / MODEL_NAME
    / "chgnet_0.3.0_e29f68s314m37.pth.tar"
  )


def _file_hash(path: Path) -> str:
  digest = hashlib.sha256()
  with path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
      digest.update(chunk)
  return digest.hexdigest()


def generate(output: Path) -> None:
  material_id = get_default_material_id()
  material = get_demo_store().get(material_id)
  if material is None or material.structure is None:
    raise SystemExit("default scorecard leader has no reconstructable structure")
  structure = material.structure.to_pymatgen()
  input_structure = material.structure.to_json_dict()
  weight_path = _weight_path()
  if not weight_path.is_file():
    raise SystemExit(f"bundled model weight file missing: {weight_path}")

  model = CHGNet.load(model_name=MODEL_NAME, use_device="cpu", verbose=False)
  optimizer = StructOptimizer(model=model, optimizer_class="FIRE", use_device="cpu")
  started = time.perf_counter()
  relaxation = optimizer.relax(
    structure,
    fmax=FMAX,
    steps=MAX_STEPS,
    relax_cell=True,
    loginterval=1,
    verbose=False,
  )
  runtime = time.perf_counter() - started
  trajectory = relaxation["trajectory"]
  final_structure = relaxation["final_structure"]
  points = []
  for index, (energy, forces, stress, cell) in enumerate(
    zip(
      trajectory.energies,
      trajectory.forces,
      trajectory.stresses,
      trajectory.cells,
      strict=True,
    )
  ):
    points.append(
      {
        "step": index,
        "energy_per_atom": float(energy) / len(structure),
        "max_force": max(
          math.sqrt(sum(float(value) ** 2 for value in vector)) for vector in forces
        ),
        "max_stress_ev_a3": max(abs(float(value)) for value in stress),
        "volume": abs(float(__import__("numpy").linalg.det(cell))),
      }
    )
  initial_volume = float(structure.volume)
  final_volume = float(final_structure.volume)
  initial_lattice = structure.lattice.abc
  final_lattice = final_structure.lattice.abc
  lattice_change = max(
    abs(final - initial) / initial * 100
    for initial, final in zip(initial_lattice, final_lattice, strict=True)
  )
  final_point = points[-1]
  artifact = {
    "artifact_version": "chgnet-reference-v1",
    "label": "cached_reference",
    "material_id": material_id,
    "formula": material.formula,
    "created_at": datetime.now(timezone.utc).isoformat(),
    "model": {
      "name": "CHGNet",
      "version": MODEL_NAME,
      "runtime_package_version": chgnet.__version__,
      "weight_filename": weight_path.name,
      "weight_checksum": _file_hash(weight_path),
    },
    "input_checksum": _canonical_hash(input_structure),
    "run": {
      "fmax_ev_a": FMAX,
      "max_steps": MAX_STEPS,
      "relax_cell": True,
      "ase_filter": "FrechetCellFilter",
      "optimizer": "FIRE",
      "device": "cpu",
      "runtime_seconds": runtime,
    },
    "result": {
      "converged": final_point["max_force"] <= FMAX,
      "steps": max(0, len(points) - 1),
      "energy_per_atom": final_point["energy_per_atom"],
      "max_force": final_point["max_force"],
      "max_stress_ev_a3": final_point["max_stress_ev_a3"],
      "initial_volume": initial_volume,
      "final_volume": final_volume,
      "volume_change_percent": (final_volume - initial_volume) / initial_volume * 100,
      "lattice_change_percent": lattice_change,
      "trajectory": points[:128],
      "relaxed_structure": {
        "lattice": final_structure.lattice.matrix.tolist(),
        "species": [str(site.specie) for site in final_structure],
        "coords": [site.frac_coords.tolist() for site in final_structure],
        "site_properties": None,
      },
    },
  }
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n")
  print(
    f"wrote {output}: {artifact['result']['steps']} steps, "
    f"{artifact['result']['max_force']:.5f} eV/A, {runtime:.2f}s"
  )


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--output", type=Path, default=Path("data/demo/chgnet_reference.json"))
  generate(parser.parse_args().output)


if __name__ == "__main__":
  main()
