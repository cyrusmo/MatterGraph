from __future__ import annotations

import json
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pymatgen.core import Lattice, Structure


class CrystalStructure(BaseModel):
  """Unit cell + fractional sites; can round-trip to :class:`pymatgen.core.Structure`."""

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

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
      if isinstance(specie, dict):
        if any(not key.strip() for key in specie):
          msg = "species mapping keys must not be empty"
          raise ValueError(msg)
        if any(value <= 0 or not math.isfinite(value) for value in specie.values()):
          msg = "species occupancies must be positive finite values"
          raise ValueError(msg)
    if self.site_properties and len(self.site_properties) != len(self.coords):
      msg = "site_properties length must match sites when set"
      raise ValueError(msg)
    return self

  def to_pymatgen(self) -> Structure:
    """Convert to a pymatgen :class:`Structure` (Cartesian built internally)."""
    sp = _site_properties_to_pymatgen(self.site_properties)
    return Structure(
      Lattice(self.lattice),
      self.species,
      self.coords,
      site_properties=sp,
    )

  @classmethod
  def from_pymatgen(cls, s: Structure) -> CrystalStructure:
    n = len(s)
    spec = [_species_to_jsonable(s[i].species) for i in range(n)]
    fracs = [list(s[i].frac_coords) for i in range(n)]
    props = [dict(s[i].properties) for i in range(n)]
    props_out = props if any(props) else None
    return cls(
      lattice=(s.lattice.matrix.tolist()),
      species=spec,  # type: ignore[arg-type]
      coords=fracs,
      site_properties=props_out,
    )

  def to_json_dict(self) -> dict[str, Any]:
    return json.loads(self.model_dump_json())


def _species_to_jsonable(species: Any) -> str | dict[str, float]:
  items = list(species.items())
  if len(items) == 1:
    sp, occ = items[0]
    if math.isclose(float(occ), 1.0):
      return str(sp)
  return {str(sp): float(occ) for sp, occ in items}


def _site_properties_to_pymatgen(
  site_properties: list[dict[str, Any] | None] | None,
) -> dict[str, list[Any]] | None:
  if not site_properties:
    return None
  keys = sorted({key for props in site_properties if props for key in props})
  if not keys:
    return None
  return {
    key: [(props or {}).get(key) for props in site_properties]
    for key in keys
  }
