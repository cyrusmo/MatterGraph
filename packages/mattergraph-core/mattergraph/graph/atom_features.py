"""Atom-level featurization helpers; extended by custom pipelines."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pymatgen.core import Structure
from pymatgen.core.periodic_table import Element


def atomic_number_one_hot(structure: Structure, max_z: int = 100) -> NDArray[np.float64]:
  n = len(structure)
  out = np.zeros((n, max_z), dtype=np.float64)
  for i, site in enumerate(structure):
    z = min(site.specie.Z, max_z) - 1
    if z >= 0:
      out[i, z] = 1.0
  return out


def covalent_radius(structure: Structure) -> NDArray[np.float64]:
  out = np.zeros((len(structure), 1), dtype=np.float64)
  for i, site in enumerate(structure):
    el: Element = site.specie.element
    r = el.atomic_radius if el and el.atomic_radius is not None else 0.0
    out[i, 0] = r
  return out
