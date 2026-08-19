import json

import pytest
from mattergraph_sim.parsers import parse_result_envelope


def test_parse_external_result_envelope() -> None:
  result = parse_result_envelope(
    json.dumps(
      {
        "engine": "lammps",
        "engine_version": "stable_29Aug2024",
        "method": "external result import",
        "parameters": {"units": "metal"},
        "input_checksum_sha256": "a" * 64,
        "output_checksum_sha256": "b" * 64,
        "converged": True,
      }
    )
  )
  assert result.engine == "lammps"
  assert result.converged is True


def test_parser_rejects_non_object_and_bad_checksum() -> None:
  with pytest.raises(ValueError, match="JSON object"):
    parse_result_envelope("[]")
  with pytest.raises(ValueError, match="64-character"):
    parse_result_envelope(
      {"engine": "custom", "method": "import", "input_checksum_sha256": "bad"}
    )
