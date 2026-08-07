"""The guard that makes connector drift a test failure rather than a discovery.

Before D1 the connector "interface" was a convention, and the four implementations had
already diverged. These tests pin the contract itself, so a sixth connector cannot quietly
invent a sixth signature.
"""

from __future__ import annotations

import ast
import inspect
import warnings
from pathlib import Path

import mattergraph_connectors
import pytest
from mattergraph.schema.property import PropertyMethod
from mattergraph_connectors.base import (
  Connector,
  ConnectorQuery,
  apply_property_filter,
  coerce_query,
  connector_provenance,
)
from mattergraph_connectors.jarvis import JarvisConnector
from mattergraph_connectors.nomad import NOMADConnector
from mattergraph_connectors.optimade import OptimadeConnector
from mattergraph_connectors.oqmd import OQMDStubConnector

# Every class-shaped connector in the package. MaterialsProjectConnector is constructed with
# an explicit key so the test never depends on MP_API_KEY being set in the environment.
_CONNECTOR_FACTORIES = {
  "jarvis": JarvisConnector,
  "nomad": NOMADConnector,
  "optimade": OptimadeConnector,
  "oqmd": OQMDStubConnector,
}


def _materials_project_connector() -> object:
  from mattergraph_connectors.materials_project import MaterialsProjectConnector

  return MaterialsProjectConnector(api_key="not-a-real-key")


@pytest.mark.parametrize("name", sorted(_CONNECTOR_FACTORIES))
def test_connectors_satisfy_the_protocol(name: str) -> None:
  connector = _CONNECTOR_FACTORIES[name]()
  assert isinstance(connector, Connector)
  assert connector.source_name == name


def test_materials_project_satisfies_the_protocol() -> None:
  connector = _materials_project_connector()
  assert isinstance(connector, Connector)
  assert connector.source_name == "materials_project"


@pytest.mark.parametrize("name", sorted(_CONNECTOR_FACTORIES))
def test_fetch_accepts_a_connector_query_first_positionally(name: str) -> None:
  """The whole point of the contract: one call shape works on every connector."""
  signature = inspect.signature(_CONNECTOR_FACTORIES[name].fetch)
  first = list(signature.parameters.values())[1]
  assert first.name == "query"
  assert first.default is None


# --- ConnectorQuery ---------------------------------------------------------------------


def test_query_strips_and_drops_empty_entries() -> None:
  query = ConnectorQuery(elements=[" Ti ", "", "  ", "O"])
  assert query.elements == ["Ti", "O"]


def test_query_collapses_an_all_blank_list_to_none() -> None:
  assert ConnectorQuery(elements=["", "  "]).elements is None


@pytest.mark.parametrize("field", ["max_records", "page_size"])
def test_query_rejects_non_positive_paging(field: str) -> None:
  with pytest.raises(ValueError, match="at least 1"):
    ConnectorQuery(**{field: 0})


def test_query_rejects_unknown_fields() -> None:
  with pytest.raises(ValueError):
    ConnectorQuery(elemnts=["Ti"])  # type: ignore[call-arg]


# --- coerce_query -----------------------------------------------------------------------


def test_coerce_query_passes_through_an_explicit_query() -> None:
  query = ConnectorQuery(elements=["Ti"], max_records=3)
  assert coerce_query(query, {}, source_name="test") is query


def test_coerce_query_returns_defaults_for_a_bare_call() -> None:
  assert coerce_query(None, {}, source_name="test") == ConnectorQuery()


def test_legacy_keywords_still_work_but_warn() -> None:
  with pytest.warns(DeprecationWarning, match="deprecated"):
    query = coerce_query(None, {"elements": ["Ti"], "max_records": 7}, source_name="test")
  assert query.elements == ["Ti"]
  assert query.max_records == 7


def test_legacy_aliases_map_onto_query_fields() -> None:
  with pytest.warns(DeprecationWarning):
    query = coerce_query(
      None, {"material_ids": ["mp-149"], "chunk_size": 5}, source_name="test"
    )
  assert query.source_ids == ["mp-149"]
  assert query.page_size == 5


def test_legacy_none_values_do_not_override_defaults() -> None:
  """`fetch(elements=["Fe"], material_ids=None)` must not clear source_ids to a bad value."""
  with pytest.warns(DeprecationWarning):
    query = coerce_query(
      None, {"elements": ["Fe"], "material_ids": None}, source_name="test"
    )
  assert query.elements == ["Fe"]
  assert query.source_ids is None


def test_mixing_a_query_and_keywords_is_a_caller_bug() -> None:
  with pytest.raises(TypeError, match="pass one or the other"):
    coerce_query(ConnectorQuery(), {"elements": ["Ti"]}, source_name="test")


def test_unknown_legacy_keyword_raises_rather_than_being_dropped() -> None:
  with pytest.raises(TypeError, match="unexpected keyword argument 'nonsense'"), pytest.warns(
    DeprecationWarning
  ):
    coerce_query(None, {"nonsense": 1}, source_name="test")


# --- provenance -------------------------------------------------------------------------


def test_connector_provenance_records_source_and_parameters() -> None:
  record = connector_provenance(
    "jarvis", source_id="JVASP-1002", parameters={"functional": "OptB88vdW"}
  )
  assert record.source == "jarvis"
  assert record.source_id == "JVASP-1002"
  assert record.method == PropertyMethod.DFT
  assert record.parameters == {"functional": "OptB88vdW"}


def test_provenance_defaults_parameters_to_none() -> None:
  assert connector_provenance("nomad").parameters is None


# --- property filtering -----------------------------------------------------------------


def _material_with(*names: str):
  from mattergraph.schema.material import Material, MaterialProperty

  return Material(
    material_id="x",
    formula="Si",
    properties=[MaterialProperty(name=n, value=1.0, source="test") for n in names],
  )


def test_property_filter_is_a_no_op_without_a_request() -> None:
  material = _material_with("density", "band_gap")
  apply_property_filter([material], ConnectorQuery(), supported=frozenset(), source_name="t")
  assert {p.name for p in material.properties} == {"density", "band_gap"}


def test_property_filter_actually_narrows_the_result() -> None:
  material = _material_with("density", "band_gap")
  apply_property_filter(
    [material],
    ConnectorQuery(properties=["density"]),
    supported=frozenset({"density", "band_gap"}),
    source_name="t",
  )
  assert [p.name for p in material.properties] == ["density"]


def test_property_filter_canonicalizes_the_request() -> None:
  """A caller asking for `k_vrh` means bulk_modulus; the filter must not drop everything."""
  material = _material_with("bulk_modulus")
  apply_property_filter(
    [material],
    ConnectorQuery(properties=["k_vrh"]),
    supported=frozenset({"bulk_modulus"}),
    source_name="t",
  )
  assert [p.name for p in material.properties] == ["bulk_modulus"]


def test_unsupported_property_request_raises_instead_of_being_ignored() -> None:
  with pytest.raises(ValueError, match="cannot return band_gap"):
    apply_property_filter(
      [_material_with("density")],
      ConnectorQuery(properties=["band_gap"]),
      supported=frozenset({"density"}),
      source_name="t",
    )


# --- the silent-empty regression --------------------------------------------------------


def test_oqmd_raises_rather_than_returning_an_empty_list() -> None:
  """An unimplemented connector must not be mistakable for a query that matched nothing."""
  with pytest.raises(NotImplementedError, match="OPTIMADE"):
    OQMDStubConnector().fetch()


def test_oqmd_raises_on_the_legacy_call_shape_too() -> None:
  with pytest.raises(NotImplementedError):
    OQMDStubConnector().fetch(elements=["Ti"])


def test_nomad_rejects_a_property_filter_it_cannot_honor() -> None:
  with pytest.raises(ValueError, match="entry metadata only"):
    NOMADConnector().fetch(ConnectorQuery(properties=["band_gap"]))


def test_jarvis_rejects_source_id_lookup_it_cannot_perform() -> None:
  with pytest.raises(ValueError, match="cannot fetch by source_ids"):
    JarvisConnector().fetch(ConnectorQuery(source_ids=["JVASP-1002"]))


# --- the three hand-maintained declarations ---------------------------------------------


def test_exports_all_and_type_checking_block_agree() -> None:
  """`_EXPORTS`, `__all__`, and the TYPE_CHECKING imports are edited by hand in three places.

  Nothing but this test notices when they drift apart.
  """
  exports = set(mattergraph_connectors._EXPORTS)
  declared = set(mattergraph_connectors.__all__)
  assert exports == declared, f"_EXPORTS vs __all__ mismatch: {exports ^ declared}"

  source = Path(mattergraph_connectors.__file__).read_text()
  tree = ast.parse(source)
  imported: set[str] = set()
  for node in ast.walk(tree):
    if isinstance(node, ast.If) and getattr(node.test, "id", None) == "TYPE_CHECKING":
      for stmt in ast.walk(node):
        if isinstance(stmt, ast.ImportFrom):
          imported.update(alias.asname or alias.name for alias in stmt.names)
  assert imported == declared, f"TYPE_CHECKING vs __all__ mismatch: {imported ^ declared}"


@pytest.mark.parametrize("name", sorted(mattergraph_connectors.__all__))
def test_every_exported_name_actually_resolves(name: str) -> None:
  # `__getattr__` memoizes into the module globals, so resolving a name here would otherwise
  # leave the lazy-import path permanently short-circuited for the rest of the session.
  was_cached = name in mattergraph_connectors.__dict__
  try:
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      assert getattr(mattergraph_connectors, name) is not None
  finally:
    if not was_cached:
      mattergraph_connectors.__dict__.pop(name, None)
