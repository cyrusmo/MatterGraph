from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
  from mattergraph_connectors.jarvis import JarvisConnector
  from mattergraph_connectors.local_csv import load_materials_from_csv
  from mattergraph_connectors.materials_project import MaterialsProjectConnector
  from mattergraph_connectors.nomad import NOMADStubConnector
  from mattergraph_connectors.oqmd import OQMDStubConnector

_EXPORTS: dict[str, tuple[str, str, str | None]] = {
  "MaterialsProjectConnector": (
    "mattergraph_connectors.materials_project",
    "MaterialsProjectConnector",
    (
      "Install the optional `mp-api` dependency or run "
      "`uv sync --all-packages --group dev` to use MaterialsProjectConnector."
    ),
  ),
  "JarvisConnector": (
    "mattergraph_connectors.jarvis",
    "JarvisConnector",
    (
      "Install the optional `jarvis-tools` dependency or run "
      "`uv sync --all-packages --group dev` to use JarvisConnector."
    ),
  ),
  "load_materials_from_csv": (
    "mattergraph_connectors.local_csv",
    "load_materials_from_csv",
    None,
  ),
  "OQMDStubConnector": (
    "mattergraph_connectors.oqmd",
    "OQMDStubConnector",
    None,
  ),
  "NOMADStubConnector": (
    "mattergraph_connectors.nomad",
    "NOMADStubConnector",
    None,
  ),
}

__all__ = [
  "MaterialsProjectConnector",
  "JarvisConnector",
  "load_materials_from_csv",
  "OQMDStubConnector",
  "NOMADStubConnector",
]


def __getattr__(name: str) -> Any:
  if name not in _EXPORTS:
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
  module_name, attr_name, hint = _EXPORTS[name]
  try:
    module = import_module(module_name)
  except ImportError as e:
    if hint is None:
      raise
    raise ImportError(hint) from e
  value = getattr(module, attr_name)
  globals()[name] = value
  return value


def __dir__() -> list[str]:
  return sorted(set(globals()) | set(__all__))
