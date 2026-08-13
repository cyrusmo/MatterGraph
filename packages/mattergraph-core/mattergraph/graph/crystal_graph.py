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
  fractional_coordinates: NDArray[np.float64]
  cartesian_coordinates: NDArray[np.float64]
  displacement_vectors: NDArray[np.float64]
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
    shell_tolerance: float = 1e-5,
  ) -> None:
    if cutoff_radius <= 0:
      raise ValueError("cutoff_radius must be positive")
    if max_neighbors <= 0:
      raise ValueError("max_neighbors must be positive")
    if shell_tolerance < 0:
      raise ValueError("shell_tolerance must be non-negative")
    self.cutoff_radius = cutoff_radius
    self.max_neighbors = max_neighbors
    self.shell_tolerance = shell_tolerance

  def _node_feature_matrix(self, structure: Structure) -> NDArray[np.float64]:
    from pymatgen.core.periodic_table import Element

    n = len(structure)
    feat_dim = 100  # up to Z=99, padding one slot; plus 3 real stats
    out = np.zeros((n, feat_dim + 3), dtype=np.float64)
    for i, site in enumerate(structure):
      z = min(site.specie.Z, 99)
      out[i, z - 1] = 1.0
      el: Element = getattr(site.specie, "element", site.specie)
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
    if not s.is_ordered:
      msg = "disordered or partially occupied sites are not supported by CrystalGraphBuilder"
      raise ValueError(msg)
    nbr = s.get_all_neighbors(self.cutoff_radius)
    n = len(s)
    selected: dict[tuple[int, int, tuple[int, int, int]], float] = {}
    truncated_sources: list[int] = []
    for i in range(n):
      pairs = sorted(
        (
          item
          for nn in nbr[i]
          if (item := _neighbor_tuple(nn))[1] > self.shell_tolerance
        ),
        key=lambda item: (item[1], item[0], item[2]),
      )
      if len(pairs) > self.max_neighbors:
        shell_limit = pairs[self.max_neighbors - 1][1]
        kept = [pair for pair in pairs if pair[1] <= shell_limit + self.shell_tolerance]
        if len(kept) < len(pairs):
          truncated_sources.append(i)
        pairs = kept
      for j, d, img in pairs:
        selected[(i, j, img)] = d

    # A periodic graph used for message passing must be reciprocal. The per-source soft cap can
    # otherwise split a tied shell in asymmetric cells, so add the exact reverse periodic edge.
    for (i, j, img), distance in list(selected.items()):
      reverse = (j, i, tuple(-value for value in img))
      selected.setdefault(reverse, distance)

    ordered_edges = sorted(
      selected.items(),
      key=lambda item: (item[0][0], item[1], item[0][1], item[0][2]),
    )
    src = [key[0] for key, _distance in ordered_edges]
    dst = [key[1] for key, _distance in ordered_edges]
    images = [key[2] for key, _distance in ordered_edges]
    dists = [distance for _key, distance in ordered_edges]
    edge_index = np.array([src, dst], dtype=np.int64) if src else np.zeros((2, 0), dtype=np.int64)
    image_offsets = np.array(images, dtype=np.int64) if images else np.zeros((0, 3), dtype=np.int64)
    fractional_coordinates = np.asarray(s.frac_coords, dtype=np.float64)
    cartesian_coordinates = np.asarray(s.cart_coords, dtype=np.float64)
    displacement_vectors = (
      np.asarray(
        [
          s.lattice.get_cartesian_coords(
            fractional_coordinates[j] + np.asarray(image) - fractional_coordinates[i]
          )
          for i, j, image in zip(src, dst, images, strict=True)
        ],
        dtype=np.float64,
      )
      if src
      else np.zeros((0, 3), dtype=np.float64)
    )
    if dists:
      dists = [float(np.linalg.norm(vector)) for vector in displacement_vectors]
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
      fractional_coordinates=fractional_coordinates,
      cartesian_coordinates=cartesian_coordinates,
      displacement_vectors=displacement_vectors,
      global_features=self._global_features(s),
      info={
        "cutoff": self.cutoff_radius,
        "max_neighbors": self.max_neighbors,
        "neighbor_target_is_soft": True,
        "complete_tied_shells": True,
        "shell_tolerance": self.shell_tolerance,
        "reciprocal": True,
        "self_loops_added": False,
        "truncated_sources": truncated_sources,
      },
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
