import importlib

import mattergraph_connectors
import pytest
from mattergraph_connectors import (
  NOMADConnector,
  NOMADConnectorError,
  NOMADHTTPError,
  NOMADMappingError,
  NOMADPayloadError,
  NOMADStubConnector,
)
from mattergraph_connectors.lematerial import LeMatBulk


def test_materials_project_connector_has_helpful_optional_dependency_error(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  module = importlib.reload(mattergraph_connectors)
  # `__getattr__` memoizes resolved names into the module globals, and `reload` re-executes
  # into the *existing* dict rather than a fresh one. So any earlier test that touched this
  # attribute leaves it cached and the lazy-import hook never fires again. Evict it.
  monkeypatch.delitem(module.__dict__, "MaterialsProjectConnector", raising=False)
  real_import_module = module.import_module

  def fake_import_module(name: str, package: str | None = None) -> object:
    if name == "mattergraph_connectors.materials_project":
      raise ImportError("No module named 'mp_api'")
    return real_import_module(name, package)

  monkeypatch.setattr(module, "import_module", fake_import_module)

  with pytest.raises(ImportError, match="mp-api"):
    _ = module.MaterialsProjectConnector


def test_lemat_bulk_from_hf_has_helpful_optional_dependency_error(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  module = importlib.import_module("mattergraph_connectors.lematerial")
  real_import_module = module.import_module

  def fake_import_module(name: str, package: str | None = None) -> object:
    if name == "datasets":
      raise ImportError("No module named 'datasets'")
    return real_import_module(name, package)

  monkeypatch.setattr(module, "import_module", fake_import_module)

  with pytest.raises(ImportError, match="optional `datasets` dependency"):
    LeMatBulk.from_hf()


def test_nomad_connector_exports_primary_and_compatibility_names() -> None:
  assert NOMADConnector.__name__ == "NOMADConnector"
  assert issubclass(NOMADHTTPError, NOMADConnectorError)
  assert issubclass(NOMADMappingError, NOMADConnectorError)
  assert issubclass(NOMADPayloadError, NOMADConnectorError)
  assert issubclass(NOMADStubConnector, NOMADConnector)
