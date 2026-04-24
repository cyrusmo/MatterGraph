from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Structure


@dataclass
class CrystalGraph:
  num_atoms: int
  node_features: NDArray[np.float64]
  edge_index: NDArray[np.int64]
  edge_features: NDArray[np.float64]
  cell: NDArray[np.float64] | None
  global_features: dict[str, float | int]
  info: dict[str, Any]


class CrystalGraphBuilder:
  """
  Build a simple crystal graph: neighbors within ``cutoff_radius``,
  node features: one-hot of atomic number (MVP) + a few element stats
  (electronegativity, covalent radius) when available.
  """

  def __init__(
    self,
    cutoff_radius: float = 5.0,
    max_neighbors: int = 12,
  ) -> None:
    self.cutoff_radius = cutoff_radius
    self.max_neighbors = max_neighbors

  def _node_feature_matrix(self, structure: Structure) -> NDArray[np.float64]:
    from pymatgen.core.periodic_table import Element

    n = len(structure)
    feat_dim = 100  # up to Z=99, padding one slot; plus 3 real stats
    out = np.zeros((n, feat_dim + 3), dtype=np.float64)
    for i, site in enumerate(structure):
      z = min(site.specie.Z, 99)
      out[i, z - 1] = 1.0
      el: Element = site.specie.element
      en = el.X if el and el.X is not None else 0.0
      r = el.atomic_radius if el and el.atomic_radius is not None else 0.0
      nval = float(getattr(el, "group", 0) or 0)
      out[i, feat_dim] = en
      out[i, feat_dim + 1] = r
      out[i, feat_dim + 2] = nval
    return out

  def _global_features(self, structure: Structure) -> dict[str, float | int]:
    d = float(structure.density)
    nsites = int(len(structure))
    spg = structure.get_space_group_info() or (None, None)
    s_num = int(spg[1]) if spg[1] is not None else 0
    return {
      "density_g_cm3": d,
      "n_sites": nsites,
      "spacegroup_number": s_num,
    }

  def build(self, material_structure: CrystalStructure) -> CrystalGraph:
    s = material_structure.to_pymatgen()
    nbr = s.get_all_neighbors(self.cutoff_radius)
    n = len(s)
    src, dst, dists = [], [], []
    for i in range(n):
      pairs: list = sorted(nbr[i], key=lambda t: t[1])[: self.max_neighbors]
      for _site, d, j, _img in pairs:
        src.append(i)
        dst.append(int(j))
        dists.append(d)
    if not src and n > 1:
      # no edges but multi-species — at least one self-loop to avoid empty tensors in pipelines
      for i in range(n):
        src.append(i)
        dst.append(i)
        dists.append(0.0)
    edge_index = np.array([src, dst], dtype=np.int64) if src else np.zeros((2, 0), dtype=np.int64)
    dists_arr = (
      np.array(dists, dtype=np.float64)[:, None] if dists else np.zeros((0, 1), dtype=np.float64)
    )
    return CrystalGraph(
      num_atoms=n,
      node_features=self._node_feature_matrix(s),
      edge_index=edge_index,
      edge_features=dists_arr,
      cell=(s.lattice.matrix if s is not None else None),
      global_features=self._global_features(s),
      info={"cutoff": self.cutoff_radius, "max_neighbors": self.max_neighbors},
    )
