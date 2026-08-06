import pytest
from mattergraph_connectors.jarvis import _jarvis_float, _row_to_material

# Shaped like a JARVIS dft_3d row: `atoms` is an Atoms.from_dict payload, and the elastic
# columns are named *_kv / *_gv and carry Voigt averages.
_ATOMS = {
  "lattice_mat": [[0.0, 2.715, 2.715], [2.715, 0.0, 2.715], [2.715, 2.715, 0.0]],
  "elements": ["Si", "Si"],
  "coords": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
  "cartesian": False,
  "props": ["", ""],
}


def _row(**overrides: object) -> dict:
  row = {
    "jid": "JVASP-1002",
    "formula": "Si",
    "atoms": _ATOMS,
    "optb88vdw_total_energy": -5.42,
    "optb88vdw_bandgap": 0.73,
    "bulk_modulus_kv": 88.9,
    "shear_modulus_gv": 62.1,
  }
  row.update(overrides)
  return row


def test_row_converts_to_a_material() -> None:
  """Regression: the connector silently returned nothing for every row.

  `Atoms.to_pymatgen` was renamed to `pymatgen_converter` upstream, and a `hasattr` guard
  turned the missing method into `None` — so `_row_to_material` returned `None` for every
  row and `fetch()` returned `[]` for every query, with no error anywhere.
  """
  material = _row_to_material("JVASP-1002", _row())

  assert material is not None, "conversion returned None — the pymatgen shim is broken"
  assert material.material_id == "jarvis:JVASP-1002"
  assert material.source_id == "JVASP-1002"
  assert material.structure is not None
  assert len(material.structure.coords) == 2


def test_elastic_columns_are_ingested_as_voigt() -> None:
  material = _row_to_material("JVASP-1002", _row())
  assert material is not None

  # The dft_3d column names are aliases, so they land under the canonical names.
  assert material.get_numeric("bulk_modulus") == pytest.approx(88.9)
  assert material.get_numeric("shear_modulus") == pytest.approx(62.1)

  bulk = material.get_property("bulk_modulus")
  assert bulk is not None
  assert bulk.unit == "GPa"
  # Voigt is an upper bound; recording it is what lets a mixed ranking column be flagged.
  assert bulk.extra["averaging_scheme"] == "voigt"


def test_na_sentinel_and_unconverged_moduli_are_skipped() -> None:
  """dft_3d marks missing values with the string "na", which float() cannot parse."""
  material = _row_to_material(
    "JVASP-1002",
    _row(bulk_modulus_kv="na", shear_modulus_gv=-1.0, optb88vdw_bandgap="na"),
  )
  assert material is not None

  names = {p.name for p in material.properties}
  assert "bulk_modulus" not in names  # "na" sentinel
  assert "shear_modulus" not in names  # non-positive: unconverged tensor
  assert "band_gap" not in names
  assert "optb88vdw_total_energy" in names


@pytest.mark.parametrize(
  ("value", "expected"),
  [
    ("na", None),
    ("N/A", None),
    ("", None),
    ("none", None),
    (None, None),
    (float("nan"), None),
    ("88.9", 88.9),
    (88.9, 88.9),
    (0, 0.0),
  ],
)
def test_jarvis_float_coercion(value: object, expected: float | None) -> None:
  assert _jarvis_float(value) == expected


def test_malformed_atoms_payload_returns_none() -> None:
  assert _row_to_material("bad", _row(atoms={"missing": "keys"})) is None
