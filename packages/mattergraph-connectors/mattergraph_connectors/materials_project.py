from __future__ import annotations

import os
from typing import Any

from mattergraph.schema.material import Material, MaterialProperty
from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Composition, Structure


def _get_api_key(key: str | None) -> str | None:
  return key or os.environ.get("MP_API_KEY") or os.environ.get("MATERIALS_PROJECT_API_KEY")


def _struct_from_mp(doc: Any) -> CrystalStructure | None:
  if doc is None or getattr(doc, "structure", None) is None:
    return None
  s: Structure = doc.structure
  return CrystalStructure.from_pymatgen(s)


def _get_rester(api_key: str) -> Any:
  try:
    from mp_api.client import MPRester  # type: ignore[import-untyped]
  except ImportError as e:
    msg = "Install the optional `mp-api` dependency to use MaterialsProjectConnector."
    raise ImportError(msg) from e
  return MPRester(api_key)


def _mp_doc_to_material(doc: Any) -> Material:
  mid = str(doc.material_id)
  formula = doc.formula_pretty
  c = Composition(formula)
  props: list[MaterialProperty] = []
  d = getattr(doc, "density", None)
  if d is not None:
    props.append(
      MaterialProperty(
        name="density",
        value=float(d),
        unit="g/cm^3",
        source="materials_project",
        method="dft",
      )
    )
  fe = getattr(doc, "formation_energy_per_atom", None)
  if fe is not None:
    props.append(
      MaterialProperty(
        name="formation_energy_per_atom",
        value=float(fe),
        unit="eV/atom",
        source="materials_project",
        method="dft",
      )
    )
  eah = getattr(doc, "energy_above_hull", None)
  if eah is not None:
    props.append(
      MaterialProperty(
        name="energy_above_hull",
        value=float(eah),
        unit="eV/atom",
        source="materials_project",
        method="dft",
      )
    )
  st = _struct_from_mp(doc)
  return Material(
    material_id=mid,
    formula=formula,
    reduced_formula=c.reduced_formula,
    structure=st,
    properties=props,
    metadata={"mp_id": mid},
  )


class MaterialsProjectConnector:
  def __init__(self, api_key: str | None = None) -> None:
    k = _get_api_key(api_key)
    if not k:
      msg = (
        "Set MP_API_KEY (or MATERIALS_PROJECT_API_KEY) or pass api_key= "
        "to MaterialsProjectConnector"
      )
      raise ValueError(msg)
    self._key = k

  def fetch(
    self,
    elements: list[str] | None = None,
    material_ids: list[str] | None = None,
    properties: list[str] | None = None,  # noqa: ARG002
    *,
    num_chunks: int = 1,
    chunk_size: int = 20,
  ) -> list[Material]:
    with _get_rester(self._key) as m:
      if material_ids:
        docs = m.materials.summary.search(
          material_ids=material_ids,  # type: ignore[call-overload, attr-defined]
          num_chunks=num_chunks,
          chunk_size=chunk_size,
          fields=None,
        )
        return [_mp_doc_to_material(d) for d in docs]
      if not elements:
        return []
      docs = m.materials.summary.search(
        elements=elements,
        num_chunks=num_chunks,
        chunk_size=chunk_size,
        fields=None,
      )  # type: ignore[call-overload, attr-defined]
      return [_mp_doc_to_material(d) for d in docs]
