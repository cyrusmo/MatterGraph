from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from mattergraph.schema.material import Material, MaterialProperty
from mattergraph.schema.structure import CrystalStructure


def load_materials_from_csv(
  path: str | Path,
  *,
  id_col: str = "material_id",
  formula_col: str = "formula",
  property_columns: list[str] | None = None,
) -> list[Material]:
  """
  Load a wide CSV: required ``material_id`` and ``formula``; optional
  ``property_columns`` (numeric columns become :class:`MaterialProperty`).
  A ``structure_json`` column with JSON ``CrystalStructure`` is supported.
  """
  p = Path(path)
  df = pd.read_csv(p)
  if id_col not in df.columns or formula_col not in df.columns:
    msg = f"CSV must have {id_col!r} and {formula_col!r} columns"
    raise ValueError(msg)
  props_list = list(property_columns) if property_columns is not None else [
    c
    for c in df.columns
    if c not in {id_col, formula_col, "structure_json"}
  ]
  out: list[Material] = []
  for _i, r in df.iterrows():
    mid = str(r[id_col])
    formula = str(r[formula_col])
    mprops: list[MaterialProperty] = []
    for c in props_list:
      if c not in r.index or pd.isna(r[c]):
        continue
      mprops.append(
        MaterialProperty(
          name=c,
          value=_coerce(r[c]),
          source="csv",
          method="unknown",
        )
      )
    st: CrystalStructure | None = None
    if "structure_json" in r.index and not pd.isna(r["structure_json"]):
      raw: Any = r["structure_json"]
      if isinstance(raw, str):
        d = json.loads(raw)
        st = CrystalStructure.model_validate(d)
    out.append(
      Material(
        material_id=mid,
        formula=formula,
        properties=mprops,
        structure=st,
        metadata={"ingest": "local_csv", "file": p.name},
      )
    )
  return out


def _coerce(v: object) -> float | str:
  if isinstance(v, (int, float)):
    return float(v)
  return str(v)
