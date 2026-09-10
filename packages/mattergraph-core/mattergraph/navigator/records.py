from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from importlib import resources
from typing import Any

import numpy as np
from mattergraph.navigator.models import NavigatorRecord, NavigatorStructure
from mattergraph.schema.material import Material
from mattergraph.schema.structure import CrystalStructure
from pymatgen.core.periodic_table import get_el_sp

ATOMIC_MASS_TABLE_VERSION = "mattergraph-atomic-masses-v1"
AVOGADRO_CONSTANT = 6.022_140_76e23


def navigator_record_from_material(
  material: Material,
  *,
  raw_record: dict[str, Any] | None = None,
) -> NavigatorRecord:
  immutable_id = (
    str(raw_record.get("immutable_id"))
    if raw_record is not None and raw_record.get("immutable_id") is not None
    else material.material_id
  )
  structure = material.structure
  nsites = len(structure.species) if structure is not None else _metadata_int(material, "nsites")
  raw_total_magnetization = _raw_numeric(raw_record, "total_magnetization")
  if raw_record is None:
    raw_total_magnetization = _numeric(material, "total_magnetization")
    if raw_total_magnetization is None:
      raw_total_magnetization = _metadata_numeric(material, "total_magnetization")
  site_moments, site_moment_failure = _site_moments(
    material,
    raw_record=raw_record,
    nsites=nsites,
  )
  maximum_force, force_failure, force_input_hash = _maximum_force(
    material,
    raw_record=raw_record,
    nsites=nsites,
  )
  density, density_failure = density_from_structure(structure)

  properties: dict[str, float | int | str | bool | None] = {
    "density": density,
    "signed_total_magnetization": raw_total_magnetization,
    "absolute_total_magnetization": (
      abs(raw_total_magnetization) if raw_total_magnetization is not None else None
    ),
    "absolute_total_magnetization_per_site": (
      abs(raw_total_magnetization) / nsites
      if raw_total_magnetization is not None and nsites > 0
      else None
    ),
    "maximum_absolute_reported_site_moment": (
      max(abs(value) for value in site_moments) if site_moments else None
    ),
    "maximum_force_norm": maximum_force,
    "raw_total_energy": _numeric(material, "energy"),
  }
  property_provenance = {
    name: {
      "source": prop.source,
      "method": str(prop.method),
      "source_id": prop.source_id,
      "unit": prop.unit,
    }
    for name in properties
    if (prop := material.get_property(_source_property_name(name))) is not None
  }
  structure_hash = (
    hashlib.sha256(
      json.dumps(
        structure.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
      ).encode("utf-8")
    ).hexdigest()
    if structure is not None
    else None
  )
  property_provenance["density"] = _derived_provenance(
    derivation_id="density-from-structure-v1",
    input_sha256=structure_hash,
    formula="cell_mass_g_per_mol / (N_A * cell_volume_angstrom3 * 1e-24)",
    unit="g/cm^3",
    failure_reason=density_failure,
    atomic_mass_table=ATOMIC_MASS_TABLE_VERSION,
  )
  if raw_total_magnetization is not None:
    raw_hash = _input_hash(raw_total_magnetization)
  else:
    raw_hash = None
  property_provenance["absolute_total_magnetization"] = _derived_provenance(
    derivation_id="absolute-total-magnetization-v1",
    input_sha256=raw_hash,
    formula="abs(total_magnetization)",
    unit="μB/cell",
    failure_reason=None if raw_total_magnetization is not None else "total magnetization missing",
  )
  property_provenance["absolute_total_magnetization_per_site"] = _derived_provenance(
    derivation_id="absolute-total-magnetization-per-site-v1",
    input_sha256=(
      _input_hash([raw_total_magnetization, nsites])
      if raw_total_magnetization is not None and nsites > 0
      else None
    ),
    formula="abs(total_magnetization) / nsites",
    unit="μB/site",
    failure_reason=(
      None
      if raw_total_magnetization is not None and nsites > 0
      else "total magnetization or valid site count missing"
    ),
  )
  property_provenance["maximum_absolute_reported_site_moment"] = _derived_provenance(
    derivation_id="maximum-absolute-site-moment-v1",
    input_sha256=_input_hash(site_moments) if site_moments else None,
    formula="max_i(abs(magnetic_moments_i))",
    unit="μB/site",
    failure_reason=site_moment_failure,
  )
  property_provenance["maximum_force_norm"] = _derived_provenance(
    derivation_id="maximum-force-norm-v1",
    input_sha256=force_input_hash,
    formula="max_i(norm(force_i))",
    unit="eV/Å",
    failure_reason=force_failure,
  )
  provenance = [item.model_dump(mode="json", exclude_none=True) for item in material.provenance]
  source = provenance[0].get("source", "unknown") if provenance else "unknown"
  source_method = provenance[0].get("method", "unknown") if provenance else "unknown"
  functional = str(material.metadata.get("functional", "pbe")).lower()
  if functional == "unknown":
    functional = "pbe"
  structure_contract = None
  if structure is not None:
    structure_contract = NavigatorStructure(
      structure_id=immutable_id,
      source_id=material.source_id or immutable_id,
      source=str(source),
      method=str(source_method),
      structure=structure,
      provenance=provenance,
    )
  return NavigatorRecord(
    material_id=immutable_id,
    formula=material.formula,
    elements=material.elements,
    nelements=len(material.elements),
    nsites=nsites,
    functional=functional,
    cross_compatibility=bool(material.metadata.get("cross_compatibility", True)),
    properties=properties,
    property_provenance=property_provenance,
    structure=structure_contract,
  )


def _source_property_name(name: str) -> str:
  aliases = {
    "maximum_force_norm": "max_force",
    "signed_total_magnetization": "total_magnetization",
    "absolute_total_magnetization": "total_magnetization",
    "absolute_total_magnetization_per_site": "total_magnetization",
    "raw_total_energy": "energy",
  }
  return aliases.get(name, name)


def _numeric(material: Material, name: str) -> float | None:
  value = material.get_numeric(name)
  return value if value is not None and math.isfinite(value) else None


def _metadata_numeric(material: Material, name: str) -> float | None:
  value = material.metadata.get(name)
  if isinstance(value, (int, float)) and math.isfinite(float(value)):
    return float(value)
  return None


def _metadata_int(material: Material, name: str) -> int:
  value = material.metadata.get(name)
  return int(value) if isinstance(value, (int, float)) and int(value) > 0 else 0


def _site_moments(
  material: Material,
  *,
  raw_record: dict[str, Any] | None,
  nsites: int,
) -> tuple[list[float], str | None]:
  if raw_record is not None:
    values = raw_record.get("magnetic_moments")
    if values is None:
      return [], "reported site moments missing"
    moments, failure = _finite_vector(values, "reported site moments")
    if moments and len(moments) != nsites:
      return [], "reported site moments must match the site count"
    return moments, failure
  metadata_value = material.metadata.get("magnetic_moments")
  values: Any = metadata_value
  prop = material.get_property("magnetic_moments")
  if prop is not None:
    values = prop.value
  if not isinstance(values, list):
    return [], "reported site moments missing"
  moments, failure = _finite_vector(values, "reported site moments")
  if moments and len(moments) != nsites:
    return [], "reported site moments must match the site count"
  return moments, failure


def _maximum_force(
  material: Material,
  *,
  raw_record: dict[str, Any] | None,
  nsites: int,
) -> tuple[float | None, str | None, str | None]:
  if raw_record is None:
    value = _numeric(material, "maximum_force_norm")
    if value is None:
      value = _numeric(material, "max_force")
    return (
      value,
      None if value is not None else "force vectors missing",
      _input_hash(value) if value is not None else None,
    )
  forces = raw_record.get("forces")
  if forces is None:
    return None, "force vectors missing", None
  try:
    vectors = np.asarray(forces, dtype=float)
  except (TypeError, ValueError):
    return None, "force vectors are not numeric", _input_hash(forces)
  input_hash = _input_hash(forces)
  if vectors.shape != (nsites, 3) or not np.isfinite(vectors).all():
    return None, "force vectors must be finite N×3 values matching the site count", input_hash
  return float(np.linalg.norm(vectors, axis=1).max()), None, input_hash


def density_from_structure(
  structure: CrystalStructure | None,
) -> tuple[float | None, str | None]:
  if structure is None:
    return None, "validated lattice and site payload missing"
  try:
    volume_angstrom3 = abs(float(np.linalg.det(np.asarray(structure.lattice, dtype=float))))
  except (TypeError, ValueError, np.linalg.LinAlgError):
    return None, "lattice volume is invalid"
  if not math.isfinite(volume_angstrom3) or volume_angstrom3 <= 0:
    return None, "lattice volume is invalid"
  masses = _atomic_masses()
  cell_mass_g_mol = 0.0
  try:
    for site in structure.species:
      entries = {site: 1.0} if isinstance(site, str) else site
      occupancy_sum = sum(float(occupancy) for occupancy in entries.values())
      if occupancy_sum <= 0 or occupancy_sum > 1.0 + 1e-8:
        return None, "site occupancies must sum to a value in (0, 1]"
      for specie, occupancy in entries.items():
        parsed = get_el_sp(specie)
        symbol = parsed.symbol if hasattr(parsed, "symbol") else parsed.element.symbol
        cell_mass_g_mol += masses[symbol] * float(occupancy)
  except (KeyError, TypeError, ValueError):
    return None, "species or occupancies are invalid for the pinned atomic-mass table"
  density = cell_mass_g_mol / AVOGADRO_CONSTANT / (volume_angstrom3 * 1e-24)
  if not math.isfinite(density) or density <= 0:
    return None, "derived density is not positive and finite"
  return density, None


@lru_cache(maxsize=1)
def _atomic_masses() -> dict[str, float]:
  table = resources.files("mattergraph.navigator").joinpath("atomic_masses_v1.json")
  return {key: float(value) for key, value in json.loads(table.read_text(encoding="utf-8")).items()}


def _raw_numeric(raw_record: dict[str, Any] | None, name: str) -> float | None:
  if raw_record is None:
    return None
  value = raw_record.get(name)
  return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None


def _finite_vector(values: Any, label: str) -> tuple[list[float], str | None]:
  if not isinstance(values, list) or not values:
    return [], f"{label} missing"
  if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in values):
    return [], f"{label} must be a finite numeric array"
  return [float(value) for value in values], None


def _input_hash(value: Any) -> str:
  return hashlib.sha256(
    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
  ).hexdigest()


def _derived_provenance(
  *,
  derivation_id: str,
  input_sha256: str | None,
  formula: str,
  unit: str,
  failure_reason: str | None,
  atomic_mass_table: str | None = None,
) -> dict[str, Any]:
  payload: dict[str, Any] = {
    "source": "MatterGraph",
    "method": "derived",
    "derivation_id": derivation_id,
    "input_sha256": input_sha256,
    "formula": formula,
    "unit": unit,
    "status": "missing" if failure_reason else "available",
    "failure_reason": failure_reason,
  }
  if atomic_mass_table:
    payload["atomic_mass_table"] = atomic_mass_table
  return payload
