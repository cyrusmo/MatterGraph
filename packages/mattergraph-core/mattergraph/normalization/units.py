"""Lightweight unit helpers (extend with pint later)."""

from __future__ import annotations


def normalize_energy_eV(value: float, from_unit: str) -> float:
  u = from_unit.lower().replace(" ", "")
  if u in ("ev", "electron volt", "electron-volt"):
    return value
  if u in ("ry", "rydberg", "rydbergs"):
    return value * 13.6056980659
  if u in ("kj/mol", "kjmol"):
    return value / 96.485332123
  if u in ("mev", "milliev"):
    return value * 0.001
  msg = f"Unsupported energy unit: {from_unit!r} (MVP: ev, rydberg, kj/mol, meV)"
  raise ValueError(msg)


def normalize_length_ang(value: float, from_unit: str) -> float:
  u = from_unit.lower()
  if u in ("ang", "angstrom", "a"):
    return value
  if u in ("nm", "nanometer", "nanometre"):
    return value * 10.0
  if u in ("bohr", "a.u.", "bohr radius"):
    return value * 0.529177210903
  msg = f"Unsupported length unit: {from_unit!r} (MVP: ang, nm, bohr)"
  raise ValueError(msg)
