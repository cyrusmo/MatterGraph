from __future__ import annotations

import json
import math
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pymatgen.core import Lattice, Structure


class CrystalStructure(BaseModel):
  """Unit cell + fractional sites; can round-trip to :class:`pymatgen.core.Structure`."""

  lattice: list[list[float]] = Field(
    ...,
    description="3x3 row-major lattice matrix (Angstrom) in the convention used by the source",
  )
  species: list[str | dict[str, float]] = Field(
    ...,
    description="Oxidation state dicts are supported, e.g. {'Li': 1, 'O': -2}.",
  )
  coords: list[list[float]] = Field(
    ...,
    description="Fractional coordinates for each site",
  )
  site_properties: list[dict[str, Any] | None] | None = None

  @model_validator(mode="after")
  def _shape(self) -> CrystalStructure:
    if len(self.lattice) != 3 or any(len(r) != 3 for r in self.lattice):
      msg = "lattice must be 3x3"
      raise ValueError(msg)
    if any(not math.isfinite(x) for row in self.lattice for x in row):
      msg = "lattice values must be finite"
      raise ValueError(msg)
    if Lattice(self.lattice).volume <= 0:
      msg = "lattice volume must be positive"
      raise ValueError(msg)
    if len(self.coords) != len(self.species):
      msg = "coords length must match species"
      raise ValueError(msg)
    if any(len(site) != 3 for site in self.coords):
      msg = "each coordinate must have length 3"
      raise ValueError(msg)
    if any(not math.isfinite(x) for site in self.coords for x in site):
      msg = "coordinate values must be finite"
      raise ValueError(msg)
    for specie in self.species:
      if isinstance(specie, str) and not specie.strip():
        msg = "species entries must not be empty"
        raise ValueError(msg)
      if isinstance(specie, dict) and not specie:
        msg = "species mapping entries must not be empty"
        raise ValueError(msg)
    if self.site_properties and len(self.site_properties) != len(self.coords):
      msg = "site_properties length must match sites when set"
      raise ValueError(msg)
    return self

  def to_pymatgen(self) -> Structure:
    """Convert to a pymatgen :class:`Structure` (Cartesian built internally)."""
    sp: Any = self.site_properties
    if not sp or len(sp) != len(self.coords):
      sp = None
    return Structure(
      Lattice(self.lattice),
      self.species,
      self.coords,
      site_properties=sp,
    )

  @classmethod
  def from_pymatgen(cls, s: Structure) -> CrystalStructure:
    n = len(s)
    spec = [str(s[i].species) for i in range(n)]
    fracs = [list(s[i].frac_coords) for i in range(n)]
    return cls(
      lattice=(s.lattice.matrix.tolist()),
      species=spec,  # type: ignore[arg-type]
      coords=fracs,
      site_properties=None,
    )

  def to_json_dict(self) -> dict[str, Any]:
    return json.loads(self.model_dump_json())
