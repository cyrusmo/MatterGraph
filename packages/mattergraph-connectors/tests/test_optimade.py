"""OPTIMADE connector tests.

Every fixture here mirrors a shape observed against the live COD or OQMD API, and each of the
first four test groups pins an upstream behaviour that silently breaks a naive implementation.
No network: the client is injected, as with the NOMAD suite.
"""

from __future__ import annotations

import math
from typing import Any

import httpx
import pytest
from mattergraph.normalization.structures import check_density, to_structure
from mattergraph_connectors.base import ConnectorQuery
from mattergraph_connectors.optimade import (
  PROVIDERS,
  OptimadeConnector,
  OptimadeHTTPError,
  OptimadePayloadError,
  _next_link,
  _row_to_material,
)


class FakeResponse:
  def __init__(self, payload: Any, *, status_code: int = 200) -> None:
    self.payload = payload
    self.status_code = status_code
    self.request = httpx.Request("GET", "https://optimade.test/v1/structures")
    self.response = httpx.Response(status_code, request=self.request)

  def raise_for_status(self) -> None:
    if self.status_code >= 400:
      raise httpx.HTTPStatusError(
        f"HTTP {self.status_code}", request=self.request, response=self.response
      )

  def json(self) -> Any:
    return self.payload


class FakeClient:
  def __init__(self, responses: list[FakeResponse] | None = None) -> None:
    self.responses = list(responses or [])
    self.calls: list[dict[str, Any]] = []
    self.closed = False

  def get(self, url: str, *, params: dict[str, Any] | None = None) -> FakeResponse:
    self.calls.append({"url": url, "params": params})
    if not self.responses:
      msg = "No fake response configured"
      raise AssertionError(msg)
    return self.responses.pop(0)

  def close(self) -> None:
    self.closed = True


# NaCl rocksalt, a = 5.64 A, 8 sites. Density is analytically checkable, which is what makes
# this fixture able to catch a wrong or transposed lattice inversion.
_A = 5.64
_NACL_LATTICE = [[_A, 0.0, 0.0], [0.0, _A, 0.0], [0.0, 0.0, _A]]
_NACL_FRAC = [
  [0.0, 0.0, 0.0],
  [0.5, 0.5, 0.0],
  [0.5, 0.0, 0.5],
  [0.0, 0.5, 0.5],
  [0.5, 0.0, 0.0],
  [0.0, 0.5, 0.0],
  [0.0, 0.0, 0.5],
  [0.5, 0.5, 0.5],
]
_NACL_CART = [[c * _A for c in site] for site in _NACL_FRAC]
# COD-style species labels: names are site labels, not element symbols.
_NACL_SPECIES_NAMES = [
  "Na1",
  "Na1_2_555",
  "Na1_3_555",
  "Na1_4_555",
  "Cl1",
  "Cl1_2_555",
  "Cl1_3_555",
  "Cl1_4_555",
]


def _nacl_attributes(**overrides: Any) -> dict[str, Any]:
  attrs: dict[str, Any] = {
    "chemical_formula_reduced": "ClNa",
    "elements": ["Cl", "Na"],
    "nsites": 8,
    "nperiodic_dimensions": 3,
    "dimension_types": [1, 1, 1],
    "structure_features": [],
    "lattice_vectors": _NACL_LATTICE,
    "cartesian_site_positions": _NACL_CART,
    "species_at_sites": list(_NACL_SPECIES_NAMES),
    "species": [
      {
        "name": name,
        "chemical_symbols": ["Na" if name.startswith("Na") else "Cl"],
        "concentration": [1.0],
      }
      for name in _NACL_SPECIES_NAMES
    ],
  }
  attrs.update(overrides)
  return attrs


def _row(entry_id: str = "1000022", **overrides: Any) -> dict[str, Any]:
  return {"id": entry_id, "type": "structures", "attributes": _nacl_attributes(**overrides)}


def _row_with(attrs: dict[str, Any], entry_id: str = "1000022") -> dict[str, Any]:
  """Build a row from an explicit attributes dict.

  Needed because `_row(**overrides)` merges into a fresh base, so a key deleted from a copy
  of `_nacl_attributes()` would silently reappear.
  """
  return {"id": entry_id, "type": "structures", "attributes": attrs}


def _attrs_without(*keys: str, **overrides: Any) -> dict[str, Any]:
  attrs = _nacl_attributes(**overrides)
  for key in keys:
    del attrs[key]
  return attrs


def _page(rows: list[dict[str, Any]], *, next_link: Any = None) -> dict[str, Any]:
  page: dict[str, Any] = {"data": rows, "meta": {"data_returned": len(rows)}}
  if next_link is not None:
    page["links"] = {"next": next_link}
  return page


def _connector(client: FakeClient, provider: str = "cod") -> OptimadeConnector:
  return OptimadeConnector(provider=provider, client=client)  # type: ignore[arg-type]


# --- trap 1: response_fields is mandatory -------------------------------------------------


def test_request_asks_for_the_fields_cod_omits_by_default() -> None:
  """COD's default response has no cartesian_site_positions, species or nsites at all."""
  client = FakeClient([FakeResponse(_page([_row()]))])
  _connector(client).fetch(ConnectorQuery(max_records=1))

  requested = client.calls[0]["params"]["response_fields"].split(",")
  for field in (
    "lattice_vectors",
    "cartesian_site_positions",
    "species",
    "species_at_sites",
    "nperiodic_dimensions",
    "chemical_formula_reduced",
  ):
    assert field in requested


def test_provider_specific_fields_are_requested_for_oqmd() -> None:
  client = FakeClient([FakeResponse(_page([_row()]))])
  _connector(client, provider="oqmd").fetch(ConnectorQuery(max_records=1))

  requested = client.calls[0]["params"]["response_fields"].split(",")
  assert "_oqmd_stability" in requested
  assert "_oqmd_band_gap" in requested


def test_elements_filter_uses_optimade_grammar() -> None:
  client = FakeClient([FakeResponse(_page([_row()]))])
  _connector(client).fetch(ConnectorQuery(elements=["Ti", "O"], max_records=1))

  assert client.calls[0]["params"]["filter"] == 'elements HAS ALL "Ti","O"'


def test_no_filter_is_sent_when_no_elements_requested() -> None:
  client = FakeClient([FakeResponse(_page([_row()]))])
  _connector(client).fetch(ConnectorQuery(max_records=1))

  assert "filter" not in client.calls[0]["params"]


# --- trap 2: links.next has two legal shapes ----------------------------------------------


@pytest.mark.parametrize(
  ("next_link", "label"),
  [
    ("https://optimade.test/v1/structures?page_offset=1", "bare string (OQMD)"),
    ({"href": "https://optimade.test/v1/structures?page_offset=1"}, "href object (COD)"),
  ],
)
def test_pagination_follows_both_next_link_shapes(next_link: Any, label: str) -> None:
  client = FakeClient(
    [
      FakeResponse(_page([_row("a")], next_link=next_link)),
      FakeResponse(_page([_row("b")])),
    ]
  )
  materials = _connector(client).fetch(ConnectorQuery(max_records=2))

  assert [m.source_id for m in materials] == ["a", "b"], f"failed for {label}"
  assert client.calls[1]["url"] == "https://optimade.test/v1/structures?page_offset=1"
  # The next link already encodes filter and paging; resending params would duplicate them.
  assert client.calls[1]["params"] is None


@pytest.mark.parametrize("links", [None, {}, {"next": None}, {"next": ""}, {"next": {}}])
def test_pagination_terminates_on_absent_or_null_next(links: Any) -> None:
  page = {"data": [_row("a")]}
  if links is not None:
    page["links"] = links
  client = FakeClient([FakeResponse(page)])

  materials = _connector(client).fetch(ConnectorQuery(max_records=10))

  assert len(materials) == 1
  assert len(client.calls) == 1


def test_next_link_helper_rejects_a_non_dict_links_block() -> None:
  assert _next_link({"data": [], "links": "not-an-object"}) is None


def test_fetch_stops_at_max_records_mid_page() -> None:
  client = FakeClient([FakeResponse(_page([_row("a"), _row("b"), _row("c")]))])
  materials = _connector(client).fetch(ConnectorQuery(max_records=2))

  assert [m.source_id for m in materials] == ["a", "b"]


# --- trap 3: species[].name is not an element symbol --------------------------------------


def test_site_labels_resolve_through_the_species_table() -> None:
  """COD names sites "Na1_2_555"; using those directly as pymatgen species fails outright."""
  material = _row_to_material(_row(), provider="cod")

  assert material.structure is not None
  assert material.reduced_formula == "NaCl"
  assert sorted(material.elements) == ["Cl", "Na"]
  assert len(material.structure.species) == 8


def test_partial_occupancy_is_preserved() -> None:
  attrs = _nacl_attributes()
  attrs["species"][0] = {
    "name": "Na1",
    "chemical_symbols": ["Na", "Cl"],
    "concentration": [0.6, 0.4],
  }
  material = _row_to_material(_row_with(attrs), provider="cod")

  assert material.structure is not None
  assert material.structure.species[0] == {"Na": 0.6, "Cl": 0.4}


def test_vacancy_reduces_occupancy_rather_than_becoming_an_element() -> None:
  attrs = _nacl_attributes()
  attrs["species"][0] = {
    "name": "Na1",
    "chemical_symbols": ["Na", "vacancy"],
    "concentration": [0.7, 0.3],
  }
  material = _row_to_material(_row_with(attrs), provider="cod")

  assert material.structure is not None
  assert material.structure.species[0] == {"Na": 0.7}


def test_unknown_site_species_is_skipped_with_a_warning() -> None:
  attrs = _nacl_attributes()
  attrs["species_at_sites"][0] = "NotInTable"
  client = FakeClient([FakeResponse(_page([_row_with(attrs, "bad"), _row("good")]))])

  with pytest.warns(RuntimeWarning, match="not in species table"):
    materials = _connector(client).fetch(ConnectorQuery(max_records=2))

  assert [m.source_id for m in materials] == ["good"]


def test_a_fully_vacant_site_is_skipped() -> None:
  attrs = _nacl_attributes()
  attrs["species"][0] = {
    "name": "Na1",
    "chemical_symbols": ["vacancy"],
    "concentration": [1.0],
  }
  client = FakeClient([FakeResponse(_page([_row_with(attrs)]))])

  with pytest.warns(RuntimeWarning, match="fully vacant"):
    assert _connector(client).fetch(ConnectorQuery(max_records=1)) == []


def test_assemblies_are_skipped_because_pymatgen_cannot_represent_them() -> None:
  client = FakeClient([FakeResponse(_page([_row(structure_features=["assemblies"])]))])

  with pytest.warns(RuntimeWarning, match="assemblies"):
    assert _connector(client).fetch(ConnectorQuery(max_records=1)) == []


# --- trap 4: cartesian vs fractional coordinates ------------------------------------------


def test_cartesian_positions_are_converted_to_fractional() -> None:
  """The failure this guards: cartesian coords validate fine and give a wrong density."""
  material = _row_to_material(_row(), provider="cod")
  assert material.structure is not None

  for actual, expected in zip(material.structure.coords, _NACL_FRAC, strict=True):
    for got, want in zip(actual, expected, strict=True):
      assert got == pytest.approx(want, abs=1e-9)


def test_derived_density_matches_the_analytic_value() -> None:
  """NaCl rocksalt, a=5.64 A, Z=4: rho = 4 * 58.44 / (N_A * a^3) ~= 2.16 g/cm^3.

  A transposed or inverted lattice would still produce a plausible-looking structure, so this
  arithmetic check is what actually pins the conversion.
  """
  material = _row_to_material(_row(), provider="cod")
  assert material.structure is not None

  expected = 4 * 58.443 / (6.02214076e23 * (_A * 1e-8) ** 3)
  density = material.get_numeric("density")
  assert density == pytest.approx(expected, rel=1e-3)

  # And the structure agrees with itself under the repo's own guardrail.
  assert check_density(material.structure, density).consistent


def test_lattice_round_trips() -> None:
  material = _row_to_material(_row(), provider="cod")
  assert material.structure is not None

  for actual, expected in zip(material.structure.lattice, _NACL_LATTICE, strict=True):
    for got, want in zip(actual, expected, strict=True):
      assert got == pytest.approx(want, abs=1e-9)


def test_density_is_labelled_derived_not_dft() -> None:
  material = _row_to_material(_row(), provider="cod")
  density = material.get_property("density")

  assert density is not None
  assert density.method == "derived"
  assert density.unit == "g/cm^3"
  assert density.extra["derived_from"] == "lattice_vectors + species_at_sites"


def test_degenerate_cell_is_rejected_rather_than_ingested() -> None:
  """Lattice.volume takes abs(), so a near-flat cell passes CrystalStructure validation."""
  flat = [[_A, 0.0, 0.0], [0.0, _A, 0.0], [0.0, 0.0, 1e-9]]
  client = FakeClient([FakeResponse(_page([_row(lattice_vectors=flat)]))])

  with pytest.warns(RuntimeWarning, match="degenerate"):
    assert _connector(client).fetch(ConnectorQuery(max_records=1)) == []


# --- dimensionality -----------------------------------------------------------------------


def test_a_slab_records_dimensionality_and_gets_no_density() -> None:
  """A vacuum-padded monolayer's bulk density measures padding, not the material."""
  client = FakeClient(
    [FakeResponse(_page([_row(nperiodic_dimensions=2, dimension_types=[1, 1, 0])]))]
  )
  materials = _connector(client).fetch(ConnectorQuery(max_records=1))

  assert len(materials) == 1
  material = materials[0]
  assert material.dimensionality == 2
  assert material.get_property("density") is None
  assert material.structure is not None, "the structure is still kept; only density is withheld"
  assert "vacuum padding" in (material.provenance[0].notes or "")


def test_dimensionality_falls_back_to_summing_dimension_types() -> None:
  attrs = _attrs_without("nperiodic_dimensions", dimension_types=[1, 1, 0])
  material = _row_to_material(_row_with(attrs), provider="cod")

  assert material.dimensionality == 2
  assert material.get_property("density") is None


def test_dimensionality_is_none_when_neither_field_is_present() -> None:
  """With no dimensionality signal at all, density is still derived rather than withheld."""
  attrs = _attrs_without("nperiodic_dimensions", "dimension_types")
  material = _row_to_material(_row_with(attrs), provider="cod")

  assert material.dimensionality is None
  assert material.get_numeric("density") is not None


def test_a_three_dimensional_record_keeps_its_density() -> None:
  material = _row_to_material(_row(), provider="cod")
  assert material.dimensionality == 3
  assert material.get_numeric("density") is not None


# --- provider properties ------------------------------------------------------------------


def test_oqmd_fields_map_onto_canonical_property_names() -> None:
  material = _row_to_material(
    _row(_oqmd_band_gap=1.85, _oqmd_delta_e=-2.11, _oqmd_stability=0.0),
    provider="oqmd",
  )

  assert material.get_numeric("band_gap") == pytest.approx(1.85)
  assert material.get_numeric("formation_energy_per_atom") == pytest.approx(-2.11)
  assert material.get_numeric("energy_above_hull") == pytest.approx(0.0)


def test_negative_oqmd_stability_survives_unclamped_and_is_flagged() -> None:
  """OQMD reports hull *distance*, which goes negative; MP's energy_above_hull never does.

  Clamping would hide a real convention mismatch inside a ranking column.
  """
  material = _row_to_material(_row(_oqmd_stability=-0.037), provider="oqmd")

  hull = material.get_property("energy_above_hull")
  assert hull is not None
  assert hull.value == pytest.approx(-0.037)
  assert hull.extra["hull_convention"] == "oqmd_hull_distance"
  assert hull.method == "dft"


def test_provider_properties_are_not_applied_to_other_providers() -> None:
  material = _row_to_material(_row(_oqmd_stability=0.5), provider="cod")
  assert material.get_property("energy_above_hull") is None


def test_missing_and_unparseable_provider_values_are_skipped() -> None:
  material = _row_to_material(
    _row(_oqmd_band_gap=None, _oqmd_delta_e="not-a-number"), provider="oqmd"
  )
  names = {p.name for p in material.properties}
  assert "band_gap" not in names
  assert "formation_energy_per_atom" not in names


def test_supported_properties_are_provider_dependent() -> None:
  client = FakeClient()
  assert _connector(client).supported_properties == frozenset({"density"})
  assert _connector(client, provider="oqmd").supported_properties == frozenset(
    {"density", "band_gap", "formation_energy_per_atom", "energy_above_hull"}
  )


def test_property_filter_rejects_what_this_provider_cannot_supply() -> None:
  client = FakeClient([FakeResponse(_page([_row()]))])
  with pytest.raises(ValueError, match="cannot return band_gap"):
    _connector(client).fetch(ConnectorQuery(properties=["band_gap"], max_records=1))


# --- degradation and errors ---------------------------------------------------------------


def test_missing_site_data_yields_a_record_without_a_structure() -> None:
  row = _row_with(_attrs_without("cartesian_site_positions"))
  client = FakeClient([FakeResponse(_page([row]))])

  with pytest.warns(RuntimeWarning, match="no structure"):
    materials = _connector(client).fetch(ConnectorQuery(max_records=1))

  assert len(materials) == 1, "the record is kept; only the structure is missing"
  assert materials[0].structure is None
  assert materials[0].get_property("density") is None


def test_null_lattice_components_yield_no_structure() -> None:
  """lattice_vectors may carry nulls in a non-periodic direction."""
  partial = [[_A, 0.0, 0.0], [0.0, _A, 0.0], [None, None, None]]
  client = FakeClient([FakeResponse(_page([_row(lattice_vectors=partial)]))])

  with pytest.warns(RuntimeWarning, match="nulls"):
    materials = _connector(client).fetch(ConnectorQuery(max_records=1))

  assert materials[0].structure is None


def test_null_reduced_formula_falls_back_to_the_cell_composition() -> None:
  """COD reports chemical_formula_reduced: null for every partially-occupied record.

  The spec requires integer proportions, so a record like "H0.572O2Ti0.858" cannot populate
  the field. Those are ordinary crystallography records; dropping them would lose all of COD's
  partial-occupancy structures.
  """
  material = _row_to_material(
    _row_with(_attrs_without("chemical_formula_reduced")), provider="cod"
  )

  assert material.reduced_formula == "NaCl"
  assert material.get_numeric("density") is not None


def test_row_with_neither_formula_nor_structure_is_skipped() -> None:
  attrs = _attrs_without("chemical_formula_reduced", "cartesian_site_positions")
  client = FakeClient([FakeResponse(_page([_row_with(attrs, "bad"), _row("good")]))])

  with pytest.warns(RuntimeWarning):
    materials = _connector(client).fetch(ConnectorQuery(max_records=2))

  assert [m.source_id for m in materials] == ["good"]


def test_anonymous_formula_is_never_used_as_a_fallback() -> None:
  """"A2B" does not raise — pymatgen parses A as a DummySpecies and writes elements=['A0+','B']."""
  attrs = _attrs_without(
    "chemical_formula_reduced", "cartesian_site_positions", chemical_formula_anonymous="A2B"
  )
  client = FakeClient([FakeResponse(_page([_row_with(attrs, "bad")]))])

  with pytest.warns(RuntimeWarning):
    assert _connector(client).fetch(ConnectorQuery(max_records=1)) == []


def test_http_failure_raises() -> None:
  client = FakeClient([FakeResponse({}, status_code=503)])
  with pytest.raises(OptimadeHTTPError, match="HTTP 503"):
    _connector(client).fetch(ConnectorQuery(max_records=1))


def test_malformed_payload_raises() -> None:
  client = FakeClient([FakeResponse({"data": "not-a-list"})])
  with pytest.raises(OptimadePayloadError, match="list under 'data'"):
    _connector(client).fetch(ConnectorQuery(max_records=1))


def test_source_id_lookup_is_rejected_rather_than_ignored() -> None:
  with pytest.raises(ValueError, match="cannot fetch by source_ids"):
    _connector(FakeClient()).fetch(ConnectorQuery(source_ids=["1000022"]))


# --- construction and provenance ----------------------------------------------------------


def test_unknown_provider_names_the_known_ones() -> None:
  with pytest.raises(ValueError, match="known providers"):
    OptimadeConnector(provider="nope")


def test_base_url_override_allows_any_provider() -> None:
  connector = OptimadeConnector(
    provider="custom", base_url="https://example.test/optimade/", client=FakeClient()  # type: ignore[arg-type]
  )
  assert connector.base_url == "https://example.test/optimade"


def test_every_listed_provider_url_is_absolute_and_unversioned() -> None:
  for name, url in PROVIDERS.items():
    assert url.startswith("http"), name
    # The version segment is appended by the connector; a baked-in /v1 would double it.
    assert not url.rstrip("/").endswith("/v1"), name


def test_ingested_material_carries_provenance() -> None:
  material = _row_to_material(_row(), provider="cod")

  assert len(material.provenance) == 1
  record = material.provenance[0]
  assert record.source == "optimade:cod"
  assert record.source_id == "1000022"
  assert record.parameters == {"provider": "cod", "nperiodic_dimensions": 3}


def test_material_id_is_namespaced_by_provider() -> None:
  assert _row_to_material(_row(), provider="cod").material_id == "cod:1000022"


def test_context_manager_closes_an_owned_client(monkeypatch: pytest.MonkeyPatch) -> None:
  client = FakeClient([FakeResponse(_page([]))])
  monkeypatch.setattr(
    "mattergraph_connectors.optimade.httpx.Client",
    lambda *a, **k: client,  # noqa: ARG005
  )

  with OptimadeConnector(provider="cod") as connector:
    assert connector.fetch(ConnectorQuery(max_records=1)) == []

  assert client.closed


def test_an_injected_client_is_not_closed() -> None:
  client = FakeClient([FakeResponse(_page([]))])
  with _connector(client) as connector:
    connector.fetch(ConnectorQuery(max_records=1))

  assert not client.closed


def test_derived_density_agrees_with_the_structure_helper() -> None:
  """The connector must not compute density by a different route than the rest of the repo."""
  material = _row_to_material(_row(), provider="cod")
  assert material.structure is not None

  assert math.isclose(
    material.get_numeric("density"),  # type: ignore[arg-type]
    float(to_structure(material.structure).density),
    rel_tol=1e-12,
  )
