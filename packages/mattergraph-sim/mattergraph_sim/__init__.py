from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
  from mattergraph_sim.ase_runner import ase_relax
  from mattergraph_sim.job_spec import AseJobSpec, SimulationJob, SimulationResult

_EXPORTS: dict[str, tuple[str, str, str | None]] = {
  "AseJobSpec": (
    "mattergraph_sim.job_spec",
    "AseJobSpec",
    None,
  ),
  "SimulationJob": (
    "mattergraph_sim.job_spec",
    "SimulationJob",
    None,
  ),
  "SimulationResult": (
    "mattergraph_sim.job_spec",
    "SimulationResult",
    None,
  ),
  "ase_relax": (
    "mattergraph_sim.ase_runner",
    "ase_relax",
    (
      "Install the optional `ase` dependency or run "
      "`uv sync --all-packages --group dev` to use ase_relax."
    ),
  ),
}

__all__ = [
  "AseJobSpec",
  "SimulationJob",
  "SimulationResult",
  "ase_relax",
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
