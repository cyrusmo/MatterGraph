from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from mattergraph.schema.property import MaterialProperty
from mattergraph.schema.provenance import ProvenanceRecord
from mattergraph.schema.structure import CrystalStructure


class Material(BaseModel):
  """Canonical, JSON-serializable material record.

  ``properties`` intentionally remains a list so multiple sources can report the same property.
  Use ``get_property`` for the first matching property, or filter the list by source/method when
  provenance matters.
  """

  model_config = ConfigDict(extra="forbid", validate_assignment=True)

  material_id: str = Field(description="Stable MatterGraph material identifier")
  formula: str = Field(description="Input chemical formula")
  reduced_formula: str = Field(default="", description="Formula reduced by pymatgen Composition")
  elements: list[str] = Field(default_factory=list, description="Sorted element symbols")
  structure: CrystalStructure | None = None
  properties: list[MaterialProperty] = Field(default_factory=list)
  provenance: list[ProvenanceRecord] = Field(default_factory=list)
  source_id: str | None = Field(
    default=None,
    description="Optional upstream material identifier, e.g. mp-149 or JVASP-1002",
  )
  metadata: dict[str, Any] = Field(default_factory=dict)

  @field_validator("material_id", "formula")
  @classmethod
  def _non_empty_strings(cls, value: str, info: Any) -> str:
    out = value.strip()
    if not out:
      msg = f"{info.field_name} must not be empty"
      raise ValueError(msg)
    return out

  @field_validator("source_id")
  @classmethod
  def _strip_source_id(cls, value: str | None) -> str | None:
    if value is None:
      return None
    out = value.strip()
    return out or None

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
      object.__setattr__(self, "reduced_formula", provided)
    else:
      object.__setattr__(self, "reduced_formula", reduced)

    derived_elements = sorted(str(e) for e in c.elements)
    if self.elements:
      provided_elements = sorted({element.strip() for element in self.elements})
      if provided_elements != derived_elements:
        msg = "elements must match formula"
        raise ValueError(msg)
      object.__setattr__(self, "elements", provided_elements)
    else:
      object.__setattr__(self, "elements", derived_elements)
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
