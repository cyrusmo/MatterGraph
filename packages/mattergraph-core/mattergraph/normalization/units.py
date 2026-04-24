"""Lightweight unit helpers (extend with pint later)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedQuantity:
  value: float
  unit: str


def normalize_energy_eV(value: float, from_unit: str) -> float:
  return normalize_energy(value, from_unit).value


def normalize_energy(value: float, from_unit: str, *, per_atom: bool = False) -> NormalizedQuantity:
  u = _clean(from_unit)
  unit = "eV/atom" if per_atom else "eV"
  if u in ("ev", "electronvolt", "electron-volt", "ev/atom", "evatom"):
    return NormalizedQuantity(value, unit)
  if u in ("ry", "rydberg", "rydbergs", "ry/atom", "rydberg/atom"):
    return NormalizedQuantity(value * 13.6056980659, unit)
  if u in ("kj/mol", "kjmol", "kjpermol"):
    return NormalizedQuantity(value / 96.485332123, unit)
  if u in ("j/mol", "jmol", "jpermol"):
    return NormalizedQuantity(value / 96485.332123, unit)
  if u in ("mev", "milliev", "mev/atom"):
    return NormalizedQuantity(value * 0.001, unit)
  msg = f"Unsupported energy unit: {from_unit!r} (supported: eV, Ry, kJ/mol, J/mol, meV)"
  raise ValueError(msg)


def normalize_length_ang(value: float, from_unit: str) -> float:
  return normalize_length(value, from_unit).value


def normalize_length(value: float, from_unit: str) -> NormalizedQuantity:
  u = _clean(from_unit)
  if u in ("ang", "angstrom", "a", "å"):
    return NormalizedQuantity(value, "angstrom")
  if u in ("nm", "nanometer", "nanometre"):
    return NormalizedQuantity(value * 10.0, "angstrom")
  if u in ("bohr", "a.u.", "bohrradius"):
    return NormalizedQuantity(value * 0.529177210903, "angstrom")
  msg = f"Unsupported length unit: {from_unit!r} (MVP: ang, nm, bohr)"
  raise ValueError(msg)


def normalize_pressure(value: float, from_unit: str) -> NormalizedQuantity:
  u = _clean(from_unit)
  if u in ("gpa",):
    return NormalizedQuantity(value, "GPa")
  if u in ("pa",):
    return NormalizedQuantity(value / 1_000_000_000.0, "GPa")
  if u in ("mpa",):
    return NormalizedQuantity(value / 1_000.0, "GPa")
  if u in ("kbar",):
    return NormalizedQuantity(value * 0.1, "GPa")
  msg = f"Unsupported pressure unit: {from_unit!r} (supported: GPa, Pa, MPa, kbar)"
  raise ValueError(msg)


def normalize_density(value: float, from_unit: str) -> NormalizedQuantity:
  u = _clean(from_unit)
  if u in ("g/cm^3", "g/cm3", "gml", "g/ml"):
    return NormalizedQuantity(value, "g/cm^3")
  if u in ("kg/m^3", "kg/m3"):
    return NormalizedQuantity(value / 1000.0, "g/cm^3")
  msg = f"Unsupported density unit: {from_unit!r} (supported: g/cm^3, kg/m^3)"
  raise ValueError(msg)


def normalize_temperature(value: float, from_unit: str) -> NormalizedQuantity:
  u = _clean(from_unit)
  if u in ("k", "kelvin"):
    return NormalizedQuantity(value, "K")
  if u in ("c", "celsius", "degc", "°c"):
    return NormalizedQuantity(value + 273.15, "K")
  msg = f"Unsupported temperature unit: {from_unit!r} (supported: K, C)"
  raise ValueError(msg)


def _clean(unit: str) -> str:
  return unit.strip().lower().replace(" ", "")
