from __future__ import annotations

import numpy as np
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


def _row_to_material(jid: str, row: dict) -> Material | None:
  from jarvis.core.atoms import Atoms  # type: ignore[import-untyped]

  try:
    a = Atoms.from_dict(row["atoms"])
  except Exception:  # noqa: BLE001
    return None
  s = a.to_pymatgen() if hasattr(a, "to_pymatgen") else None
  if s is None or not isinstance(s, Structure):
    return None
  st = CrystalStructure.from_pymatgen(s)
  props: list[MaterialProperty] = []
  d = row.get("optb88vdw_total_energy")
  if d is not None and not (isinstance(d, float) and np.isnan(d)):
    props.append(
      MaterialProperty(
        name="optb88vdw_total_energy",
        value=float(d),
        unit="eV",
        source="jarvis",
        method="dft",
      )
    )
  eg = row.get("optb88vdw_bandgap")
  if eg is not None and not (isinstance(eg, float) and np.isnan(eg)):
    props.append(
      MaterialProperty(
        name="optb88vdw_bandgap",
        value=float(eg),
        unit="eV",
        source="jarvis",
        method="dft",
      )
    )
  f = str(row.get("formula", "UNK"))
  return Material(
    material_id=f"jarvis:{jid}",
    formula=f,
    properties=props,
    structure=st,
    metadata={"jid": jid, "source": "jarvis_dft_3d"},
  )
