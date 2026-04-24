import importlib

import mattergraph_sim
import pytest


def test_ase_relax_has_helpful_optional_dependency_error(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  module = importlib.reload(mattergraph_sim)
  real_import_module = module.import_module

  def fake_import_module(name: str, package: str | None = None) -> object:
    if name == "mattergraph_sim.ase_runner":
      raise ImportError("No module named 'ase'")
    return real_import_module(name, package)

  monkeypatch.setattr(module, "import_module", fake_import_module)

  with pytest.raises(ImportError, match="optional `ase`"):
    _ = module.ase_relax
