from types import SimpleNamespace

import pytest
from mattergraph_connectors.materials_project import _mp_doc_to_material, _vrh


def _doc(**overrides: object) -> SimpleNamespace:
  """A stand-in for emmet's SummaryDoc.

  `_mp_doc_to_material` reads everything but `material_id` and `formula_pretty` through
  `getattr(doc, ..., None)`, so a namespace with the fields under test is enough — no
  network and no MPRester.
  """
  fields: dict[str, object] = {
    "material_id": "mp-149",
    "formula_pretty": "Si",
    "density": 2.33,
    "formation_energy_per_atom": 0.0,
    "energy_above_hull": 0.0,
    # Both moduli arrive as dicts of averaging conventions, not floats.
    "bulk_modulus": {"voigt": 89.0, "reuss": 88.0, "vrh": 88.5},
    "shear_modulus": {"voigt": 63.0, "reuss": 61.0, "vrh": 62.0},
    "homogeneous_poisson": 0.22,
    "universal_anisotropy": 0.03,
  }
  fields.update(overrides)
  return SimpleNamespace(**fields)


def test_elastic_moduli_are_ingested_as_vrh() -> None:
  material = _mp_doc_to_material(_doc())

  assert material.get_numeric("bulk_modulus") == pytest.approx(88.5)
  assert material.get_numeric("shear_modulus") == pytest.approx(62.0)

  bulk = material.get_property("bulk_modulus")
  assert bulk is not None
  assert bulk.unit == "GPa"
  assert bulk.method == "dft"
  assert bulk.extra["averaging_scheme"] == "vrh"


def test_tensor_summaries_land_in_metadata() -> None:
  material = _mp_doc_to_material(_doc())

  # Poisson ratio and anisotropy describe the whole tensor rather than one property.
  assert material.metadata["homogeneous_poisson"] == pytest.approx(0.22)
  assert material.metadata["universal_anisotropy"] == pytest.approx(0.03)
  assert material.metadata["mp_id"] == "mp-149"
  assert material.source_id == "mp-149"


def test_doc_without_an_elastic_tensor_is_not_an_error() -> None:
  """Most MP entries have no elastic tensor, so absence is the common path."""
  material = _mp_doc_to_material(
    _doc(bulk_modulus=None, shear_modulus=None, homogeneous_poisson=None,
         universal_anisotropy=None)
  )

  names = {p.name for p in material.properties}
  assert "bulk_modulus" not in names
  assert "shear_modulus" not in names
  assert "density" in names
  assert "homogeneous_poisson" not in material.metadata


@pytest.mark.parametrize(
  ("raw", "expected"),
  [
    (None, None),
    ({}, None),
    ({"voigt": 1.0}, None),  # present but no VRH average
    ({"vrh": None}, None),
    ({"vrh": "not-a-number"}, None),
    ({"vrh": 5}, 5.0),
    (88.5, None),  # a bare float is not the documented shape
  ],
)
def test_vrh_extraction(raw: object, expected: float | None) -> None:
  assert _vrh(raw) == expected
