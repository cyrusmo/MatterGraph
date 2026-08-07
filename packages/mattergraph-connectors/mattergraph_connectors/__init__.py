from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
  from mattergraph_connectors.base import (
    Connector,
    ConnectorQuery,
    apply_property_filter,
    coerce_query,
    connector_provenance,
  )
  from mattergraph_connectors.jarvis import JarvisConnector
  from mattergraph_connectors.lematerial import LeMatBulk
  from mattergraph_connectors.local_csv import load_materials_from_csv
  from mattergraph_connectors.materials_project import MaterialsProjectConnector
  from mattergraph_connectors.nomad import (
    NOMADConnector,
    NOMADConnectorError,
    NOMADHTTPError,
    NOMADMappingError,
    NOMADPayloadError,
    NOMADStubConnector,
  )
  from mattergraph_connectors.optimade import (
    PROVIDERS,
    OptimadeConnector,
    OptimadeConnectorError,
    OptimadeHTTPError,
    OptimadeMappingError,
    OptimadePayloadError,
  )
  from mattergraph_connectors.oqmd import OQMDStubConnector

_EXPORTS: dict[str, tuple[str, str, str | None]] = {
  "Connector": ("mattergraph_connectors.base", "Connector", None),
  "ConnectorQuery": ("mattergraph_connectors.base", "ConnectorQuery", None),
  "apply_property_filter": ("mattergraph_connectors.base", "apply_property_filter", None),
  "coerce_query": ("mattergraph_connectors.base", "coerce_query", None),
  "connector_provenance": ("mattergraph_connectors.base", "connector_provenance", None),
  "MaterialsProjectConnector": (
    "mattergraph_connectors.materials_project",
    "MaterialsProjectConnector",
    (
      "MaterialsProjectConnector needs the optional `mp-api` dependency: install the extra "
      "with `pip install 'mattergraph-connectors[mp]'`, or run "
      "`uv sync --all-packages --group dev` for a full workspace environment."
    ),
  ),
  "JarvisConnector": (
    "mattergraph_connectors.jarvis",
    "JarvisConnector",
    (
      "JarvisConnector needs the optional `jarvis-tools` dependency: install the extra "
      "with `pip install 'mattergraph-connectors[jarvis]'`, or run "
      "`uv sync --all-packages --group dev` for a full workspace environment."
    ),
  ),
  "load_materials_from_csv": (
    "mattergraph_connectors.local_csv",
    "load_materials_from_csv",
    None,
  ),
  "LeMatBulk": (
    "mattergraph_connectors.lematerial",
    "LeMatBulk",
    None,
  ),
  "OQMDStubConnector": (
    "mattergraph_connectors.oqmd",
    "OQMDStubConnector",
    None,
  ),
  "NOMADConnector": (
    "mattergraph_connectors.nomad",
    "NOMADConnector",
    None,
  ),
  "NOMADConnectorError": (
    "mattergraph_connectors.nomad",
    "NOMADConnectorError",
    None,
  ),
  "NOMADHTTPError": (
    "mattergraph_connectors.nomad",
    "NOMADHTTPError",
    None,
  ),
  "NOMADMappingError": (
    "mattergraph_connectors.nomad",
    "NOMADMappingError",
    None,
  ),
  "NOMADPayloadError": (
    "mattergraph_connectors.nomad",
    "NOMADPayloadError",
    None,
  ),
  "NOMADStubConnector": (
    "mattergraph_connectors.nomad",
    "NOMADStubConnector",
    None,
  ),
  "OptimadeConnector": ("mattergraph_connectors.optimade", "OptimadeConnector", None),
  "OptimadeConnectorError": (
    "mattergraph_connectors.optimade",
    "OptimadeConnectorError",
    None,
  ),
  "OptimadeHTTPError": ("mattergraph_connectors.optimade", "OptimadeHTTPError", None),
  "OptimadeMappingError": ("mattergraph_connectors.optimade", "OptimadeMappingError", None),
  "OptimadePayloadError": ("mattergraph_connectors.optimade", "OptimadePayloadError", None),
  "PROVIDERS": ("mattergraph_connectors.optimade", "PROVIDERS", None),
}

__all__ = [
  "Connector",
  "ConnectorQuery",
  "apply_property_filter",
  "coerce_query",
  "connector_provenance",
  "MaterialsProjectConnector",
  "JarvisConnector",
  "LeMatBulk",
  "load_materials_from_csv",
  "OQMDStubConnector",
  "NOMADConnector",
  "NOMADConnectorError",
  "NOMADHTTPError",
  "NOMADMappingError",
  "NOMADPayloadError",
  "NOMADStubConnector",
  "OptimadeConnector",
  "OptimadeConnectorError",
  "OptimadeHTTPError",
  "OptimadeMappingError",
  "OptimadePayloadError",
  "PROVIDERS",
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
