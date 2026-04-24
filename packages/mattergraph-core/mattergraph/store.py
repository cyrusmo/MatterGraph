from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from mattergraph.schema.material import Material, MaterialProperty, ProvenanceRecord
from mattergraph.schema.structure import CrystalStructure


class MaterialStore:
  """In-memory store of :class:`Material` records, typically loaded from JSON/JSONL."""

  def __init__(self, materials: list[Material] | None = None) -> None:
    self._materials: list[Material] = list(materials or [])

  @property
  def materials(self) -> list[Material]:
    return self._materials

  def __iter__(self) -> Iterator[Material]:
    return iter(self._materials)

  def get(self, material_id: str) -> Material | None:
    for m in self._materials:
      if m.material_id == material_id:
        return m
    return None

  @classmethod
  def from_jsonl(
    cls,
    path: str | Path,
    *,
    max_rows: int | None = None,
  ) -> MaterialStore:
    p = Path(path)
    out: list[Material] = []
    with p.open() as f:
      for n, line in enumerate(f):
        if max_rows is not None and n >= max_rows:
          break
        line = line.strip()
        if not line:
          continue
        d = json.loads(line)
        out.append(_material_from_dict(d))
    return cls(out)

  @classmethod
  def from_demo(cls) -> MaterialStore:
    here = Path(__file__).resolve().parent
    # demo next to install: use env or CWD
    for candidate in [
      Path("data/demo/materials_sample.jsonl"),
      here / "../../../data/demo/materials_sample.jsonl",
    ]:
      p = Path(candidate)
      if p.is_file():
        return cls.from_jsonl(p)
    return cls([])


def _material_from_dict(d: dict[str, Any]) -> Material:
  props: list[MaterialProperty] = []
  for p in d.get("properties", []):
    props.append(
      MaterialProperty(
        name=p.get("name", ""),
        value=p.get("value"),
        unit=p.get("unit"),
        source=p.get("source", "unknown"),
        method=p.get("method", "unknown"),
        confidence=p.get("confidence"),
        uncertainty=p.get("uncertainty"),
        extra={k: v for k, v in p.items() if k not in {"name", "value", "unit", "source", "method"}},
      )
    )
  prov: list[ProvenanceRecord] = [
    ProvenanceRecord(
      source=x.get("source", ""),
      method=x.get("method", "unknown"),
      confidence=x.get("confidence"),
      notes=x.get("notes"),
    )
    for x in d.get("provenance", [])
  ]
  st = None
  if d.get("structure"):
    st = CrystalStructure.model_validate(d["structure"])
  return Material(
    material_id=d.get("material_id", ""),
    formula=d.get("formula", ""),
    reduced_formula=d.get("reduced_formula", "") or d.get("formula", ""),
    elements=list(d.get("elements", [])),
    structure=st,
    properties=props,
    provenance=prov,
    metadata=dict(d.get("metadata", {})),
  )
