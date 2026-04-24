from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from mattergraph.graph.atom_features import basic_atom_features
from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Structure


@dataclass
class CrystalGraph:
  """Deterministic graph representation of a periodic crystal.

  ``edge_features`` columns are: distance (Angstrom), image_a, image_b, image_c.
  ``image_offsets`` repeats the integer periodic image offset columns for direct access.
  """

  num_atoms: int
  node_features: NDArray[np.float64]
  edge_index: NDArray[np.int64]
  edge_features: NDArray[np.float64]
  image_offsets: NDArray[np.int64]
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
    src: list[int] = []
    dst: list[int] = []
    dists: list[float] = []
    images: list[tuple[int, int, int]] = []
    for i in range(n):
      pairs = sorted(
        (_neighbor_tuple(nn) for nn in nbr[i]),
        key=lambda item: (item[1], item[0], item[2]),
      )[: self.max_neighbors]
      for j, d, img in pairs:
        src.append(i)
        dst.append(j)
        dists.append(d)
        images.append(img)
    if not src and n > 1:
      # no edges but multi-species — at least one self-loop to avoid empty tensors in pipelines
      for i in range(n):
        src.append(i)
        dst.append(i)
        dists.append(0.0)
        images.append((0, 0, 0))
    edge_index = np.array([src, dst], dtype=np.int64) if src else np.zeros((2, 0), dtype=np.int64)
    image_offsets = np.array(images, dtype=np.int64) if images else np.zeros((0, 3), dtype=np.int64)
    dists_arr = (
      np.array(dists, dtype=np.float64)[:, None] if dists else np.zeros((0, 1), dtype=np.float64)
    )
    edge_features = (
      np.hstack([dists_arr, image_offsets.astype(np.float64)])
      if len(dists)
      else np.zeros((0, 4), dtype=np.float64)
    )
    return CrystalGraph(
      num_atoms=n,
      node_features=basic_atom_features(s),
      edge_index=edge_index,
      edge_features=edge_features,
      image_offsets=image_offsets,
      cell=(s.lattice.matrix if s is not None else None),
      global_features=self._global_features(s),
      info={"cutoff": self.cutoff_radius, "max_neighbors": self.max_neighbors},
    )


def _neighbor_tuple(neighbor: Any) -> tuple[int, float, tuple[int, int, int]]:
  """Extract a deterministic (index, distance, image) tuple across pymatgen versions."""
  if hasattr(neighbor, "index"):
    index = int(neighbor.index)
    distance = float(neighbor.nn_distance)
    image = tuple(int(x) for x in neighbor.image)
    return index, distance, image  # type: ignore[return-value]
  _site, distance, index, image = neighbor
  return int(index), float(distance), tuple(int(x) for x in image)  # type: ignore[return-value]
