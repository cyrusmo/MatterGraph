from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.structure import CrystalStructure


class MaterialProperty(BaseModel):
  name: str
  value: float | str | dict[str, Any]
  unit: str | None = None
  source: str = "unknown"
  method: str = "unknown"  # dft, experimental, model_predicted, unknown
  confidence: float | None = None
  uncertainty: float | None = None
  extra: dict[str, Any] = Field(default_factory=dict)


class Material(BaseModel):
  material_id: str
  formula: str
  reduced_formula: str = Field(default="")
  elements: list[str] = Field(default_factory=list)
  structure: CrystalStructure | None = None
  properties: list[MaterialProperty] = Field(default_factory=list)
  provenance: list[ProvenanceRecord] = Field(default_factory=list)
  metadata: dict[str, Any] = Field(default_factory=dict)

  @model_validator(mode="after")
  def _backfill(self) -> Material:
    from pymatgen.core import Composition

    c = Composition(self.formula)
    if not self.reduced_formula:
      self.reduced_formula = c.reduced_formula
    if not self.elements:
      self.elements = sorted(str(e) for e in c.elements)
    return self

  def get_property(self, name: str) -> MaterialProperty | None:
    n = name.lower()
    for p in self.properties:
      if p.name.lower() == n:
        return p
    return None

  def get_numeric(self, name: str) -> float | None:
    p = self.get_property(name)
    if p is None:
      return None
    if isinstance(p.value, (int, float)):
      return float(p.value)
    if isinstance(p.value, str):
      try:
        return float(p.value)
      except ValueError:
        return None
    return None
