from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from mattergraph.schema.property import MaterialProperty
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.structure import CrystalStructure


class Material(BaseModel):
  material_id: str
  formula: str
  reduced_formula: str = Field(default="")
  elements: list[str] = Field(default_factory=list)
  structure: CrystalStructure | None = None
  properties: list[MaterialProperty] = Field(default_factory=list)
  provenance: list[ProvenanceRecord] = Field(default_factory=list)
  metadata: dict[str, Any] = Field(default_factory=dict)

  @field_validator("material_id", "formula")
  @classmethod
  def _non_empty_strings(cls, value: str, info: Any) -> str:
    out = value.strip()
    if not out:
      msg = f"{info.field_name} must not be empty"
      raise ValueError(msg)
    return out

  @model_validator(mode="after")
  def _backfill(self) -> Material:
    from pymatgen.core import Composition

    c = Composition(self.formula)
    reduced = c.reduced_formula
    if self.reduced_formula:
      provided = Composition(self.reduced_formula).reduced_formula
      if provided != reduced:
        msg = "reduced_formula must match formula"
        raise ValueError(msg)
      self.reduced_formula = provided
    else:
      self.reduced_formula = reduced

    derived_elements = sorted(str(e) for e in c.elements)
    if self.elements:
      provided_elements = sorted({element.strip() for element in self.elements})
      if provided_elements != derived_elements:
        msg = "elements must match formula"
        raise ValueError(msg)
      self.elements = provided_elements
    else:
      self.elements = derived_elements
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
