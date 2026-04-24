from __future__ import annotations

from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Structure


def to_structure(cs: CrystalStructure) -> Structure:
  return cs.to_pymatgen()
