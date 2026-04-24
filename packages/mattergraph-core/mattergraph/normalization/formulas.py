from __future__ import annotations

from pymatgen.core import Composition


def standardize_formula(formula: str) -> str:
  """ICSD-like string form; primarily composition-normalized."""
  return str(Composition(formula)).replace(" ", "")


def reduced_formula(formula: str) -> str:
  return Composition(formula).reduced_formula
