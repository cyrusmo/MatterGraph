from __future__ import annotations

from dataclasses import dataclass

from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Structure

# A structure and its stated density should agree to within the difference between a 0 K
# relaxed cell and a room-temperature measurement — a few percent. Anything larger is a
# record defect, not thermal expansion.
DENSITY_TOLERANCE = 0.05


@dataclass(frozen=True)
class DensityCheck:
  """Result of comparing a stated density against the one its own cell implies."""

  computed: float
  stated: float
  ratio: float
  consistent: bool
  diagnosis: str | None = None


def to_structure(cs: CrystalStructure) -> Structure:
  return cs.to_pymatgen()


def check_density(
  cs: CrystalStructure,
  stated_density: float,
  *,
  tolerance: float = DENSITY_TOLERANCE,
) -> DensityCheck:
  """Cross-check a stated density (g/cm^3) against the cell and composition.

  This is the cheapest consistency check available on a materials record, and it catches
  the most common structural defect: a conventional cell written with an incomplete basis.
  A dropped body-center atom shows up as a ratio near 2, a partial fcc basis as a ratio
  near 4 — so a near-integer ratio names the specific failure.
  """
  computed = float(to_structure(cs).density)
  if computed <= 0 or stated_density <= 0:
    msg = "densities must be positive"
    raise ValueError(msg)

  ratio = stated_density / computed
  consistent = abs(ratio - 1.0) <= tolerance
  diagnosis = None
  if not consistent:
    nearest = round(ratio)
    if nearest >= 2 and abs(ratio - nearest) <= 0.1:
      diagnosis = (
        f"stated density is ~{nearest}x the cell's own density; the cell likely holds "
        f"1/{nearest} of its basis atoms"
      )
    else:
      diagnosis = f"stated density and cell disagree by {abs(ratio - 1.0):.1%}"
  return DensityCheck(
    computed=computed,
    stated=stated_density,
    ratio=ratio,
    consistent=consistent,
    diagnosis=diagnosis,
  )
