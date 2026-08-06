from __future__ import annotations

import math
from typing import Any

from mattergraph.schema.material import Material, MaterialProperty
from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Composition, Structure


class JarvisConnector:
  """
  Fetches a subset of the JARVIS-DFT 3D database via ``jarvis.db.figshare``.

  The full dataset is large; this connector is for MVP experimentation.
  """

  def __init__(self) -> None:
    self._dft3d: list[dict] | None = None

  def _load(self) -> list[dict]:
    if self._dft3d is None:
      from jarvis.db.figshare import data  # type: ignore[import-untyped]

      self._dft3d = data("dft_3d")
    return self._dft3d

  def fetch(
    self,
    elements: list[str] | None = None,
    *,
    max_records: int = 50,
  ) -> list[Material]:
    rows = self._load()
    out: list[Material] = []
    want = {e.strip() for e in elements} if elements else set()
    for row in rows:
      if len(out) >= max_records:
        break
      f = str(row.get("formula", ""))
      if want:
        try:
          c = Composition(f)
        except Exception:  # noqa: BLE001
          continue
        el_in = {str(x) for x in c.elements}
        if el_in.isdisjoint(want):
          continue
      mat = _row_to_material(str(row.get("jid", "unknown")), row)
      if mat is not None:
        out.append(mat)
    return out


def _jarvis_float(value: Any) -> float | None:
  """Coerce a dft_3d cell to a float, or ``None`` when it carries no value.

  dft_3d marks missing entries with the **string** ``"na"``, not NaN, so a plain
  ``isnan`` guard misses them and ``float("na")`` raises.
  """
  if value is None:
    return None
  if isinstance(value, str):
    if value.strip().lower() in {"na", "n/a", "", "none"}:
      return None
  try:
    out = float(value)
  except (TypeError, ValueError):
    return None
  return None if math.isnan(out) else out


def _to_pymatgen(atoms: Any) -> Structure | None:
  """Convert a JARVIS ``Atoms`` to a pymatgen ``Structure`` across library versions.

  jarvis-tools names this ``pymatgen_converter``; older releases exposed ``to_pymatgen``.
  Missing *both* is a real failure and must not be swallowed into "no data" — that is
  precisely how this connector silently returned an empty list for every query.
  """
  for method_name in ("pymatgen_converter", "to_pymatgen"):
    method = getattr(atoms, method_name, None)
    if callable(method):
      converted = method()
      return converted if isinstance(converted, Structure) else None
  msg = (
    "JARVIS Atoms exposes neither pymatgen_converter() nor to_pymatgen(); "
    "the installed jarvis-tools version is not supported."
  )
  raise AttributeError(msg)


def _row_to_material(jid: str, row: dict) -> Material | None:
  from jarvis.core.atoms import Atoms  # type: ignore[import-untyped]

  try:
    a = Atoms.from_dict(row["atoms"])
  except Exception:  # noqa: BLE001
    return None
  s = _to_pymatgen(a)
  if s is None:
    return None
  st = CrystalStructure.from_pymatgen(s)

  props: list[MaterialProperty] = []
  for name, unit in (("optb88vdw_total_energy", "eV"), ("optb88vdw_bandgap", "eV")):
    value = _jarvis_float(row.get(name))
    if value is not None:
      props.append(
        MaterialProperty(name=name, value=value, unit=unit, source="jarvis", method="dft")
      )

  # dft_3d reports Voigt averages, an upper bound, where Materials Project reports VRH.
  # Record the scheme so a ranking column mixing the two can be flagged rather than
  # silently biasing JARVIS candidates high. Non-positive values mark unconverged entries.
  for column, name in (("bulk_modulus_kv", "bulk_modulus"), ("shear_modulus_gv", "shear_modulus")):
    value = _jarvis_float(row.get(column))
    if value is not None and value > 0:
      props.append(
        MaterialProperty(
          name=name,
          value=value,
          unit="GPa",
          source="jarvis",
          method="dft",
          extra={"averaging_scheme": "voigt"},
        )
      )

  f = str(row.get("formula", "UNK"))
  return Material(
    material_id=f"jarvis:{jid}",
    formula=f,
    properties=props,
    structure=st,
    source_id=jid,
    metadata={"jid": jid, "source": "jarvis_dft_3d"},
  )
