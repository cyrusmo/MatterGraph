from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
  from mattergraph_benchmarks.discovery_metrics import dcg, ndcg_at_k
  from mattergraph_benchmarks.matbench_adapter import matbench_dataframe, matbench_regression
  from mattergraph_benchmarks.uncertainty import coverage_at_target
  from mattergraph_benchmarks.validation_split import stratified_regression_split

_EXPORTS: dict[str, tuple[str, str, str | None]] = {
  "matbench_dataframe": (
    "mattergraph_benchmarks.matbench_adapter",
    "matbench_dataframe",
    None,
  ),
  "matbench_regression": (
    "mattergraph_benchmarks.matbench_adapter",
    "matbench_regression",
    None,
  ),
  "ndcg_at_k": (
    "mattergraph_benchmarks.discovery_metrics",
    "ndcg_at_k",
    None,
  ),
  "dcg": (
    "mattergraph_benchmarks.discovery_metrics",
    "dcg",
    None,
  ),
  "coverage_at_target": (
    "mattergraph_benchmarks.uncertainty",
    "coverage_at_target",
    None,
  ),
  "stratified_regression_split": (
    "mattergraph_benchmarks.validation_split",
    "stratified_regression_split",
    (
      "Install the optional `scikit-learn` dependency or run "
      "`uv sync --all-packages --group dev` to use stratified_regression_split."
    ),
  ),
}

__all__ = [
  "matbench_dataframe",
  "matbench_regression",
  "ndcg_at_k",
  "dcg",
  "coverage_at_target",
  "stratified_regression_split",
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
