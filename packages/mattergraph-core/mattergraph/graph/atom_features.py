"""Atom-level featurization helpers; extended by custom pipelines."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from pymatgen.core import Structure
from pymatgen.core.periodic_table import Element


ATOM_FEATURE_LABELS = (
  *tuple(f"Z_{z}" for z in range(1, 101)),
  "electronegativity",
  "atomic_radius",
  "periodic_table_group",
)


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
    el: Element = getattr(site.specie, "element", site.specie)
    r = el.atomic_radius if el and el.atomic_radius is not None else 0.0
    out[i, 0] = r
  return out


def basic_atom_features(structure: Structure, max_z: int = 100) -> NDArray[np.float64]:
  """Deterministic MVP atom features used by :class:`CrystalGraphBuilder`.

  Columns are atomic-number one-hot features followed by electronegativity, atomic radius,
  and periodic-table group. Missing elemental data is encoded as ``0.0``.
  """
  n = len(structure)
  out = np.zeros((n, max_z + 3), dtype=np.float64)
  one_hot = atomic_number_one_hot(structure, max_z=max_z)
  out[:, :max_z] = one_hot
  for i, site in enumerate(structure):
    el: Element = getattr(site.specie, "element", site.specie)
    out[i, max_z] = el.X if el and el.X is not None else 0.0
    out[i, max_z + 1] = el.atomic_radius if el and el.atomic_radius is not None else 0.0
    out[i, max_z + 2] = float(getattr(el, "group", 0) or 0)
  return out
