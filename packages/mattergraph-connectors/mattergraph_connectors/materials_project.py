from __future__ import annotations

import math
import os
from typing import Any

from mattergraph.schema.material import Material, MaterialProperty
from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Composition, Structure

from mattergraph_connectors.base import (
  ConnectorQuery,
  apply_property_filter,
  coerce_query,
  connector_provenance,
)

SOURCE_NAME = "materials_project"

# The old fetch() default for chunk_size, preserved so legacy callers page identically.
_DEFAULT_CHUNK_SIZE = 20

# The property names _mp_doc_to_material actually maps. Anything outside this set cannot be
# returned no matter what the caller asks for, so a request for one is an error rather than
# something to quietly drop.
SUPPORTED_PROPERTIES = frozenset(
  {
    "density",
    "formation_energy_per_atom",
    "energy_above_hull",
    "bulk_modulus",
    "shear_modulus",
  }
)


def _get_api_key(key: str | None) -> str | None:
  return key or os.environ.get("MP_API_KEY") or os.environ.get("MATERIALS_PROJECT_API_KEY")


def _struct_from_mp(doc: Any) -> CrystalStructure | None:
  if doc is None or getattr(doc, "structure", None) is None:
    return None
  s: Structure = doc.structure
  return CrystalStructure.from_pymatgen(s)


def _vrh(raw: Any) -> float | None:
  """Pull the Voigt-Reuss-Hill average out of an MP modulus field.

  ``SummaryDoc.bulk_modulus`` and ``.shear_modulus`` are ``dict[str, float] | None``
  holding ``voigt``/``reuss``/``vrh``, not plain floats. Most MP entries have no elastic
  tensor at all, so ``None`` is the common path rather than an error case.
  """
  if not isinstance(raw, dict):
    return None
  value = raw.get("vrh")
  if value is None:
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


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
  for name, raw in (
    ("bulk_modulus", getattr(doc, "bulk_modulus", None)),
    ("shear_modulus", getattr(doc, "shear_modulus", None)),
  ):
    value = _vrh(raw)
    if value is not None:
      props.append(
        MaterialProperty(
          name=name,
          value=value,
          unit="GPa",
          source="materials_project",
          method="dft",
          extra={"averaging_scheme": "vrh"},
        )
      )

  st = _struct_from_mp(doc)
  # Poisson ratio and elastic anisotropy summarize the whole tensor rather than describing
  # one property, so they live in metadata. Scorecard constraints can still match them via
  # the `equals` branch, and MP's own Poisson ratio cross-checks the derived one.
  metadata: dict[str, Any] = {"mp_id": mid}
  for key in ("homogeneous_poisson", "universal_anisotropy"):
    raw = getattr(doc, key, None)
    if raw is not None:
      metadata[key] = float(raw)

  return Material(
    material_id=mid,
    formula=formula,
    reduced_formula=c.reduced_formula,
    structure=st,
    properties=props,
    provenance=[
      connector_provenance(
        SOURCE_NAME,
        source_id=mid,
        notes="Materials Project summary document",
      )
    ],
    source_id=mid,
    metadata=metadata,
  )


class MaterialsProjectConnector:
  """Read Materials Project summary documents and normalize them to MatterGraph materials."""

  source_name = SOURCE_NAME

  def __init__(self, api_key: str | None = None) -> None:
    k = _get_api_key(api_key)
    if not k:
      msg = (
        "Set MP_API_KEY (or MATERIALS_PROJECT_API_KEY) or pass api_key= "
        "to MaterialsProjectConnector"
      )
      raise ValueError(msg)
    self._key = k

  def fetch(self, query: ConnectorQuery | None = None, **legacy: Any) -> list[Material]:
    # num_chunks is MP transport, not part of the general query: the old signature bounded a
    # result at num_chunks * chunk_size, which ConnectorQuery expresses as max_records.
    num_chunks = legacy.pop("num_chunks", None)
    if num_chunks is not None:
      if query is not None:
        msg = "MaterialsProjectConnector.fetch() got both a ConnectorQuery and num_chunks"
        raise TypeError(msg)
      # chunk_size is the legacy alias for page_size, so checking only "page_size" here
      # would let the default silently overwrite an explicit chunk_size.
      if "page_size" not in legacy and "chunk_size" not in legacy:
        legacy["page_size"] = _DEFAULT_CHUNK_SIZE
    q = coerce_query(query, legacy, source_name=SOURCE_NAME)
    if num_chunks is not None:
      q = q.model_copy(update={"max_records": max(1, int(num_chunks)) * q.page_size})
    return self._fetch(q)

  def _fetch(self, query: ConnectorQuery) -> list[Material]:
    chunks = math.ceil(query.max_records / query.page_size)
    with _get_rester(self._key) as m:
      if query.source_ids:
        docs = m.materials.summary.search(
          material_ids=list(query.source_ids),  # type: ignore[call-overload, attr-defined]
          num_chunks=chunks,
          chunk_size=query.page_size,
          fields=None,
        )
      elif query.elements:
        docs = m.materials.summary.search(
          elements=list(query.elements),
          num_chunks=chunks,
          chunk_size=query.page_size,
          fields=None,
        )  # type: ignore[call-overload, attr-defined]
      else:
        return []
    materials = [_mp_doc_to_material(d) for d in docs][: query.max_records]
    return apply_property_filter(
      materials, query, supported=SUPPORTED_PROPERTIES, source_name=SOURCE_NAME
    )
