from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PropertyDefinition:
  name: str
  preferred_unit: str | None
  aliases: tuple[str, ...] = ()


PROPERTY_DEFINITIONS: dict[str, PropertyDefinition] = {
  "density": PropertyDefinition("density", "g/cm^3", ("rho", "mass_density")),
  "formation_energy_per_atom": PropertyDefinition(
    "formation_energy_per_atom",
    "eV/atom",
    ("formation_energy", "formation_energy_pa", "e_form", "eform"),
  ),
  "energy_above_hull": PropertyDefinition(
    "energy_above_hull",
    "eV/atom",
    ("e_above_hull", "e_hull", "ehull", "energy_above_hull_per_atom"),
  ),
  # JARVIS dft_3d names its moduli *_kv / *_gv; both are Voigt averages rather than VRH, so
  # ingesting connectors record the averaging scheme in MaterialProperty.extra.
  "bulk_modulus": PropertyDefinition(
    "bulk_modulus", "GPa", ("k_vrh", "kvrh", "bulk_modulus_kv")
  ),
  "shear_modulus": PropertyDefinition(
    "shear_modulus", "GPa", ("g_vrh", "gvrh", "shear_modulus_gv")
  ),
  "band_gap": PropertyDefinition("band_gap", "eV", ("bandgap", "gap", "optb88vdw_bandgap")),
  # Derived from bulk and shear moduli by mattergraph.derived.elastic. Canonical so that
  # Scorecard can rank on them rather than leaving them stranded in a dataclass.
  "youngs_modulus": PropertyDefinition(
    "youngs_modulus", "GPa", ("young_modulus", "youngs", "e_modulus")
  ),
  "poisson_ratio": PropertyDefinition(
    "poisson_ratio", None, ("poisson", "nu", "homogeneous_poisson")
  ),
  "specific_stiffness": PropertyDefinition(
    "specific_stiffness", "MN*m/kg", ("specific_modulus",)
  ),
}

_ALIASES: dict[str, str] = {}
for _name, _definition in PROPERTY_DEFINITIONS.items():
  _ALIASES[_name] = _name
  for _alias in _definition.aliases:
    _ALIASES[_alias] = _name


def canonical_property_name(name: str) -> str:
  """Normalize common source aliases into MatterGraph's v0.1 property names."""
  key = name.strip().lower().replace("-", "_").replace(" ", "_")
  return _ALIASES.get(key, key)


def preferred_unit(name: str) -> str | None:
  definition = PROPERTY_DEFINITIONS.get(canonical_property_name(name))
  return definition.preferred_unit if definition else None
