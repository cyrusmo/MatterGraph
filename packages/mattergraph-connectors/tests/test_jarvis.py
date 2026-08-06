import pytest
from mattergraph_connectors.base import ConnectorQuery
from mattergraph_connectors.jarvis import JarvisConnector, _jarvis_float, _row_to_material

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


def test_ingested_material_carries_provenance() -> None:
  """Before D1 every ingested material had an empty `provenance` list."""
  material = _row_to_material("JVASP-1002", _row())
  assert material is not None

  assert len(material.provenance) == 1
  record = material.provenance[0]
  assert record.source == "jarvis"
  assert record.source_id == "JVASP-1002"
  # The functional is what makes a mixed-source ranking column detectable.
  assert record.parameters == {"dataset": "dft_3d", "functional": "OptB88vdW"}


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


# --- fetch() orchestration --------------------------------------------------------------
# `fetch` and `_load` were never executed by any test before D1. Stubbing `_load` exercises
# the element filter and record cap without the multi-hundred-MB figshare download.


def _connector(rows: list[dict]) -> JarvisConnector:
  connector = JarvisConnector()
  connector._dft3d = rows
  return connector


def test_fetch_filters_by_element() -> None:
  rows = [_row(), _row(jid="JVASP-2", formula="Al2O3")]
  materials = _connector(rows).fetch(ConnectorQuery(elements=["Si"]))

  assert [m.source_id for m in materials] == ["JVASP-1002"]


def test_fetch_caps_at_max_records() -> None:
  rows = [_row(jid=f"JVASP-{i}") for i in range(5)]
  assert len(_connector(rows).fetch(ConnectorQuery(max_records=2))) == 2


def test_fetch_skips_rows_with_an_unparseable_formula() -> None:
  rows = [_row(formula="!!not-a-formula!!"), _row(jid="JVASP-2")]
  materials = _connector(rows).fetch(ConnectorQuery(elements=["Si"]))

  assert [m.source_id for m in materials] == ["JVASP-2"]


def test_fetch_honors_a_property_filter() -> None:
  materials = _connector([_row()]).fetch(ConnectorQuery(properties=["bulk_modulus"]))
  assert [p.name for p in materials[0].properties] == ["bulk_modulus"]


def test_fetch_rejects_a_property_it_cannot_supply() -> None:
  with pytest.raises(ValueError, match="cannot return density"):
    _connector([_row()]).fetch(ConnectorQuery(properties=["density"]))


def test_legacy_keyword_call_still_works() -> None:
  """`examples/02_ingest_jarvis.py` still calls fetch this way."""
  rows = [_row(jid=f"JVASP-{i}") for i in range(5)]
  with pytest.warns(DeprecationWarning):
    materials = _connector(rows).fetch(max_records=3)
  assert len(materials) == 3
