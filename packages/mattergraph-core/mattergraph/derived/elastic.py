"""Isotropic elastic quantities derived from bulk and shear moduli.

Everything here is transparent arithmetic on two properties the schema already carries.
Nothing is fitted, and nothing is imputed: if a modulus is missing, the result is ``None``
rather than a guess.

**These are stiffness quantities, not strength.** Yield strength, hardness, and fracture
toughness are governed by microstructure — grain size, precipitates, dislocation density,
prior cold work — none of which this schema holds. Two heat treatments of one alloy can
differ fivefold in yield strength while E, K, and G barely move.

One consequence worth knowing before you screen on it: specific stiffness (E/rho) is
nearly identical across structural metals — about 26 MN*m/kg for aluminium, titanium, and
steel alike. It will not separate a metals shortlist. Those are separated by strength,
corrosion resistance, and cost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from mattergraph.normalization.units import normalize_density, normalize_pressure
from mattergraph.schema.material import Material
from mattergraph.schema.property import MaterialProperty, PropertyMethod

Ductility = Literal["ductile", "borderline", "brittle"]

# Poisson's ratio thresholds. Pugh's ratio is a 1:1 monotone map of these, so the
# equivalent G/K cuts (0.435 and 0.75) bracket the conventional Pugh value of ~0.57 rather
# than contradicting it.
DUCTILE_POISSON = 0.31
BRITTLE_POISSON = 0.20

# Above this, E collapses toward zero and E/rho becomes numerically unstable.
_POISSON_INCOMPRESSIBLE_WARN = 0.48


@dataclass(frozen=True)
class ElasticDerived:
  """Isotropic elastic quantities derived from a single (K, G) pair."""

  bulk_modulus: float
  shear_modulus: float
  youngs_modulus: float
  poisson_ratio: float
  pugh_ratio: float
  ductility: Ductility
  specific_stiffness: float | None = None
  method: PropertyMethod = PropertyMethod.UNKNOWN
  warnings: tuple[str, ...] = ()


def _ductility(poisson: float) -> Ductility:
  if poisson >= DUCTILE_POISSON:
    return "ductile"
  if poisson <= BRITTLE_POISSON:
    return "brittle"
  return "borderline"


def derive_elastic(
  bulk_modulus: float,
  shear_modulus: float,
  density: float | None = None,
) -> ElasticDerived:
  """Derive Young's modulus, Poisson's ratio, Pugh's ratio, and specific stiffness.

  ``bulk_modulus`` and ``shear_modulus`` are in GPa, ``density`` in g/cm^3. Raises
  ``ValueError`` for input a solid cannot have, rather than returning a number that would
  rank as a legitimate candidate.
  """
  k = float(bulk_modulus)
  g = float(shear_modulus)

  # Born stability for an isotropic solid. Emitting these would be worse than refusing:
  # a negative Young's modulus entering a `maximize` objective simply ranks last and looks
  # like a real result.
  if not math.isfinite(k) or not math.isfinite(g):
    msg = "bulk and shear moduli must be finite"
    raise ValueError(msg)
  if k <= 0 or g <= 0:
    msg = (
      f"bulk and shear moduli must be positive for a stable solid (got K={k}, G={g}); "
      "non-positive values usually mean an unconverged elastic tensor"
    )
    raise ValueError(msg)

  denominator = 3.0 * k + g
  if denominator == 0:
    msg = "3K + G must be non-zero"
    raise ValueError(msg)

  youngs = 9.0 * k * g / denominator
  poisson = (3.0 * k - 2.0 * g) / (2.0 * denominator)
  pugh = g / k

  warnings: list[str] = []
  if poisson < 0:
    warnings.append(
      f"negative Poisson ratio ({poisson:.3f}): auxetic behaviour is real but essentially "
      "unknown among bulk metals, so this usually indicates a badly converged elastic tensor"
    )
  if poisson > _POISSON_INCOMPRESSIBLE_WARN:
    warnings.append(
      f"Poisson ratio {poisson:.3f} approaches the incompressible limit of 0.5; "
      "Young's modulus and specific stiffness are numerically unstable here"
    )

  specific_stiffness = None
  if density is not None:
    rho = float(density)
    if rho > 0 and math.isfinite(rho):
      # GPa / (g/cm^3) == MN*m/kg
      specific_stiffness = youngs / rho
    else:
      warnings.append(f"density {density!r} is not usable; specific stiffness omitted")

  return ElasticDerived(
    bulk_modulus=k,
    shear_modulus=g,
    youngs_modulus=youngs,
    poisson_ratio=poisson,
    pugh_ratio=pugh,
    ductility=_ductility(poisson),
    specific_stiffness=specific_stiffness,
    warnings=tuple(warnings),
  )


def _as_gpa(prop: MaterialProperty, warnings: list[str]) -> float | None:
  value = prop.value
  if not isinstance(value, (int, float)):
    return None
  if prop.unit is None:
    # local_csv ingestion writes unit=None for every column. A K in GPa against a G in MPa
    # gives a Pugh ratio wrong by 1000x that still looks like a plausible number.
    warnings.append(f"{prop.name} has no unit; assuming GPa")
    return float(value)
  try:
    return normalize_pressure(float(value), prop.unit).value
  except ValueError as exc:
    warnings.append(str(exc))
    return None


def derive_elastic_for(material: Material) -> ElasticDerived | None:
  """Derive elastic quantities for a material, or ``None`` if either modulus is absent.

  Never imputes a missing modulus. Records where the numbers came from: ``method`` is
  ``dft`` only when both inputs are DFT, since a ratio built from a computed modulus and a
  measured one is a chimera.
  """
  bulk = material.get_property("bulk_modulus")
  shear = material.get_property("shear_modulus")
  if bulk is None or shear is None:
    return None

  warnings: list[str] = []
  k = _as_gpa(bulk, warnings)
  g = _as_gpa(shear, warnings)
  if k is None or g is None:
    return None

  schemes = {
    prop.extra.get("averaging_scheme")
    for prop in (bulk, shear)
    if prop.extra.get("averaging_scheme")
  }
  if len(schemes) > 1:
    warnings.append(
      f"bulk and shear moduli use different averaging schemes ({', '.join(sorted(schemes))}); "
      "Voigt is an upper bound and VRH is not, so the derived values mix conventions"
    )

  density = material.get_numeric("density")
  density_prop = material.get_property("density")
  if density is not None and density_prop is not None and density_prop.unit is not None:
    try:
      density = normalize_density(density, density_prop.unit).value
    except ValueError as exc:
      warnings.append(str(exc))
      density = None

  try:
    derived = derive_elastic(k, g, density)
  except ValueError as exc:
    warnings.append(str(exc))
    return None

  methods = {str(bulk.method), str(shear.method)}
  method = PropertyMethod(next(iter(methods))) if len(methods) == 1 else PropertyMethod.UNKNOWN

  return ElasticDerived(
    **{**derived.__dict__, "method": method, "warnings": (*warnings, *derived.warnings)}
  )


def elastic_frame(materials: list[Material]) -> pd.DataFrame:
  """Derived elastic quantities for every material that has both moduli.

  Returns a :class:`pandas.DataFrame` shaped like :meth:`Scorecard.rank` output so the two
  compose. Materials lacking either modulus are omitted — check the row count against the
  pool size before drawing conclusions.
  """
  columns = [
    "material_id",
    "bulk_modulus",
    "shear_modulus",
    "youngs_modulus",
    "poisson_ratio",
    "pugh_ratio",
    "ductility",
    "specific_stiffness",
    "method",
    "warnings",
  ]
  rows: list[dict[str, Any]] = []
  for material in materials:
    derived = derive_elastic_for(material)
    if derived is None:
      continue
    rows.append(
      {
        "material_id": material.material_id,
        "bulk_modulus": derived.bulk_modulus,
        "shear_modulus": derived.shear_modulus,
        "youngs_modulus": derived.youngs_modulus,
        "poisson_ratio": derived.poisson_ratio,
        "pugh_ratio": derived.pugh_ratio,
        "ductility": derived.ductility,
        "specific_stiffness": derived.specific_stiffness,
        "method": PropertyMethod(derived.method).value,
        "warnings": "; ".join(derived.warnings),
      }
    )
  if not rows:
    return pd.DataFrame(columns=columns)
  return pd.DataFrame(rows, columns=columns)


def with_derived_properties(material: Material) -> Material:
  """Return a copy carrying the derived quantities as ranked-on-able properties.

  Non-mutating: ``Material`` sets ``validate_assignment=True`` and ``extra="forbid"``, so
  this returns a ``model_copy`` and leaves the input untouched. Returns the material
  unchanged when either modulus is missing.
  """
  derived = derive_elastic_for(material)
  if derived is None:
    return material

  extra = {"derivation": "mattergraph.derived.elastic", "pugh_ratio": derived.pugh_ratio}
  added = [
    MaterialProperty(
      name="youngs_modulus",
      value=derived.youngs_modulus,
      unit="GPa",
      source="derived:mattergraph",
      method=derived.method,
      extra=extra,
    ),
    MaterialProperty(
      name="poisson_ratio",
      value=derived.poisson_ratio,
      unit=None,
      source="derived:mattergraph",
      method=derived.method,
      extra={**extra, "ductility": derived.ductility},
    ),
  ]
  if derived.specific_stiffness is not None:
    added.append(
      MaterialProperty(
        name="specific_stiffness",
        value=derived.specific_stiffness,
        unit="MN*m/kg",
        source="derived:mattergraph",
        method=derived.method,
        extra=extra,
      )
    )
  return material.model_copy(update={"properties": [*material.properties, *added]})
