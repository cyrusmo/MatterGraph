import importlib

import mattergraph_benchmarks
import pytest


def test_stratified_split_has_helpful_optional_dependency_error(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  module = importlib.reload(mattergraph_benchmarks)
  real_import_module = module.import_module

  def fake_import_module(name: str, package: str | None = None) -> object:
    if name == "mattergraph_benchmarks.validation_split":
      raise ImportError("No module named 'sklearn'")
    return real_import_module(name, package)

  monkeypatch.setattr(module, "import_module", fake_import_module)

  with pytest.raises(ImportError, match="scikit-learn"):
    _ = module.stratified_regression_split
