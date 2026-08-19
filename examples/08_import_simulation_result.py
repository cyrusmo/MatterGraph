"""Validate a compact result artifact produced outside MatterGraph."""

import json

from mattergraph_sim.parsers import parse_result_envelope

payload = {
  "engine": "lammps",
  "engine_version": "stable_29Aug2024",
  "method": "external result import",
  "parameters": {"units": "metal", "timestep_fs": 1.0},
  "input_checksum_sha256": "a" * 64,
  "output_checksum_sha256": "b" * 64,
  "converged": True,
  "properties": [],
  "artifacts": [],
  "provenance": [],
}

result = parse_result_envelope(json.dumps(payload))
print(result.model_dump_json(indent=2))
