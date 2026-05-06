import importlib

import mattergraph_connectors
import pytest
from mattergraph_connectors.lematerial import LeMatBulk


def test_materials_project_connector_has_helpful_optional_dependency_error(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  module = importlib.reload(mattergraph_connectors)
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
