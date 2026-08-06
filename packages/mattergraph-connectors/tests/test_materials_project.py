from types import SimpleNamespace
from typing import Any

import pytest
from mattergraph_connectors import materials_project as mp_module
from mattergraph_connectors.base import ConnectorQuery
from mattergraph_connectors.materials_project import (
  MaterialsProjectConnector,
  _mp_doc_to_material,
  _vrh,
)


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


def test_ingested_material_carries_provenance() -> None:
  """Before D1 every ingested material had an empty `provenance` list."""
  material = _mp_doc_to_material(_doc())

  assert len(material.provenance) == 1
  record = material.provenance[0]
  assert record.source == "materials_project"
  assert record.source_id == "mp-149"
  assert record.method == "dft"


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


# --- fetch() orchestration --------------------------------------------------------------
# `fetch` was never executed by any test before D1: the suite only covered the private
# mappers. These exercise the paging math, the branch selection, and the property filter
# against a fake rester, so no network and no MP_API_KEY are involved.


class _FakeSearch:
  def __init__(self, docs: list[SimpleNamespace]) -> None:
    self.docs = docs
    self.calls: list[dict[str, Any]] = []

  def search(self, **kwargs: Any) -> list[SimpleNamespace]:
    self.calls.append(kwargs)
    return self.docs


class _FakeRester:
  def __init__(self, docs: list[SimpleNamespace]) -> None:
    self.summary = _FakeSearch(docs)
    self.materials = SimpleNamespace(summary=self.summary)

  def __enter__(self) -> "_FakeRester":
    return self

  def __exit__(self, *exc: object) -> None:
    return None


@pytest.fixture
def fake_rester(monkeypatch: pytest.MonkeyPatch) -> _FakeRester:
  rester = _FakeRester([_doc(material_id="mp-149"), _doc(material_id="mp-8062")])
  monkeypatch.setattr(mp_module, "_get_rester", lambda key: rester)  # noqa: ARG005
  return rester


def _connector() -> MaterialsProjectConnector:
  return MaterialsProjectConnector(api_key="not-a-real-key")


def test_fetch_by_elements_maps_paging_onto_mp_chunks(fake_rester: _FakeRester) -> None:
  materials = _connector().fetch(ConnectorQuery(elements=["Si"], max_records=10, page_size=5))

  call = fake_rester.summary.calls[0]
  assert call["elements"] == ["Si"]
  assert call["chunk_size"] == 5
  assert call["num_chunks"] == 2  # ceil(10 / 5)
  assert len(materials) == 2


def test_fetch_truncates_to_max_records(fake_rester: _FakeRester) -> None:
  materials = _connector().fetch(ConnectorQuery(elements=["Si"], max_records=1))
  assert len(materials) == 1


def test_fetch_by_source_ids_uses_the_material_ids_branch(fake_rester: _FakeRester) -> None:
  _connector().fetch(ConnectorQuery(source_ids=["mp-149"]))
  assert fake_rester.summary.calls[0]["material_ids"] == ["mp-149"]


def test_fetch_without_a_filter_returns_nothing_and_makes_no_call(
  fake_rester: _FakeRester,
) -> None:
  assert _connector().fetch(ConnectorQuery()) == []
  assert fake_rester.summary.calls == []


def test_fetch_honors_a_property_filter(fake_rester: _FakeRester) -> None:
  """Regression: `properties=` was accepted and silently discarded."""
  materials = _connector().fetch(
    ConnectorQuery(elements=["Si"], properties=["density"])
  )
  assert [p.name for p in materials[0].properties] == ["density"]


def test_fetch_rejects_a_property_it_cannot_supply(fake_rester: _FakeRester) -> None:
  with pytest.raises(ValueError, match="cannot return band_gap"):
    _connector().fetch(ConnectorQuery(elements=["Si"], properties=["band_gap"]))


def test_legacy_keyword_call_preserves_old_chunking(fake_rester: _FakeRester) -> None:
  """`scripts/ingest_materials_project.py` still calls fetch this way."""
  with pytest.warns(DeprecationWarning):
    _connector().fetch(elements=["Fe", "Ti"], chunk_size=5, num_chunks=1)

  call = fake_rester.summary.calls[0]
  assert call["chunk_size"] == 5
  assert call["num_chunks"] == 1


def test_legacy_material_ids_keyword_still_routes_correctly(fake_rester: _FakeRester) -> None:
  with pytest.warns(DeprecationWarning):
    _connector().fetch(elements=["Fe"], material_ids=["mp-149"], chunk_size=5, num_chunks=1)
  assert fake_rester.summary.calls[0]["material_ids"] == ["mp-149"]
