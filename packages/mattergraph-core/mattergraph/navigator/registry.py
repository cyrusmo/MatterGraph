from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Iterable

import numpy as np

from mattergraph.navigator.models import (
  ConstraintKind,
  ConstraintOperator,
  NavigatorRecord,
  PropertyRegistry,
  RegistryEntry,
)

REGISTRY_VERSION = "navigator-registry-v1"


def canonical_json(value: object) -> str:
  return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def canonical_digest(value: object) -> str:
  return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def default_registry(*, index_id: str) -> PropertyRegistry:
  numeric = [
    RegistryEntry(
      field="nelements",
      label="Element count",
      kind=ConstraintKind.CATEGORICAL,
      executable=True,
      unit="count",
      operators=_numeric_operators(),
      source="source_native",
      comparability_scope="compatible_pbe",
      missingness="required source field",
      relaxable=True,
      bounds=(1.0, 12.0),
    ),
    RegistryEntry(
      field="nsites",
      label="Site count",
      kind=ConstraintKind.CATEGORICAL,
      executable=True,
      unit="count",
      operators=_numeric_operators(),
      source="source_native",
      comparability_scope="compatible_pbe",
      missingness="required source field",
      relaxable=True,
      bounds=(1.0, 256.0),
    ),
    RegistryEntry(
      field="density",
      label="Derived density",
      kind=ConstraintKind.PHYSICAL,
      executable=True,
      unit="g/cm^3",
      operators=_numeric_operators(),
      source="deterministically_derived",
      derivation_id="density-from-structure-v1",
      comparability_scope="valid 3D structures",
      missingness="unknown when lattice, occupancy, or species validation fails",
      relaxable=True,
      bounds=(0.0, 25.0),
    ),
    RegistryEntry(
      field="absolute_total_magnetization",
      label="Absolute net cell magnetization",
      kind=ConstraintKind.PHYSICAL,
      executable=True,
      unit="μB/cell",
      operators=_numeric_operators(),
      source="deterministically_derived",
      derivation_id="absolute-total-magnetization-v1",
      comparability_scope="explicit net-cell requests within compatible_pbe",
      missingness="unknown when total magnetization is not reported",
      relaxable=True,
      confirmation_required=True,
      bounds=(0.0, 100.0),
      scientific_note=(
        "Net cell magnetization can be near zero while opposing local moments remain large."
      ),
    ),
    RegistryEntry(
      field="absolute_total_magnetization_per_site",
      label="Absolute net magnetization per site",
      kind=ConstraintKind.PHYSICAL,
      executable=True,
      unit="μB/site",
      operators=_numeric_operators(),
      source="deterministically_derived",
      derivation_id="absolute-total-magnetization-per-site-v1",
      comparability_scope="size-normalized compatible_pbe records",
      missingness="unknown when total magnetization or site count is unavailable",
      relaxable=True,
      confirmation_required=True,
      bounds=(0.0, 10.0),
    ),
    RegistryEntry(
      field="maximum_absolute_reported_site_moment",
      label="Maximum absolute reported site moment",
      kind=ConstraintKind.PHYSICAL,
      executable=True,
      unit="μB/site",
      operators=_numeric_operators(),
      source="deterministically_derived",
      derivation_id="maximum-absolute-site-moment-v1",
      comparability_scope="records with reported site moments",
      missingness="unknown when local moments are not reported",
      relaxable=True,
      confirmation_required=True,
      bounds=(0.0, 10.0),
    ),
    RegistryEntry(
      field="maximum_force_norm",
      label="Maximum atomic force norm",
      kind=ConstraintKind.CALCULATION_QUALITY,
      executable=True,
      unit="eV/Å",
      operators=_numeric_operators(),
      source="deterministically_derived",
      derivation_id="maximum-force-norm-v1",
      comparability_scope="calculation-quality gate within compatible_pbe",
      missingness="unknown when force vectors are not reported",
      relaxable=True,
      bounds=(0.0, 5.0),
      scientific_note="Relaxing this gate admits less-converged calculations.",
    ),
  ]
  entries = [
    RegistryEntry(
      field="formula",
      label="Formula",
      kind=ConstraintKind.CATEGORICAL,
      executable=True,
      unit=None,
      operators=[ConstraintOperator.EQ],
      source="source_native",
      comparability_scope="compatible_pbe",
      missingness="required source field",
      relaxable=True,
    ),
    RegistryEntry(
      field="elements",
      label="Included or excluded elements",
      kind=ConstraintKind.CATEGORICAL,
      executable=True,
      unit=None,
      operators=[ConstraintOperator.INCLUDE_ALL, ConstraintOperator.EXCLUDE_ANY],
      source="source_native",
      comparability_scope="compatible_pbe",
      missingness="derived from validated formula",
      relaxable=True,
    ),
    *numeric,
    RegistryEntry(
      field="functional",
      label="Functional",
      kind=ConstraintKind.CATEGORICAL,
      executable=True,
      unit=None,
      operators=[ConstraintOperator.EQ],
      source="source_native_index_invariant",
      comparability_scope="compatible_pbe only",
      missingness="required index invariant",
      relaxable=False,
      supported_values=["pbe"],
    ),
    RegistryEntry(
      field="cross_compatibility",
      label="Compatibility marker",
      kind=ConstraintKind.EVIDENCE,
      executable=True,
      unit=None,
      operators=[ConstraintOperator.EQ],
      source="source_native_index_invariant",
      comparability_scope="compatible_pbe only",
      missingness="required index invariant",
      relaxable=False,
      supported_values=["true"],
    ),
    RegistryEntry(
      field="signed_total_magnetization",
      label="Raw signed total magnetization",
      kind=ConstraintKind.EVIDENCE,
      executable=False,
      unit="μB/cell",
      operators=[],
      source="source_native",
      comparability_scope="display only",
      missingness="may be absent",
      relaxable=False,
      display_only=True,
      scientific_note="The sign generally reflects an arbitrary spin orientation.",
    ),
    RegistryEntry(
      field="raw_total_energy",
      label="Raw total energy",
      kind=ConstraintKind.EVIDENCE,
      executable=False,
      unit="eV",
      operators=[],
      source="source_native",
      comparability_scope="display only; never across unrelated compositions",
      missingness="may be absent",
      relaxable=False,
      display_only=True,
    ),
    RegistryEntry(
      field="energy_above_hull",
      label="Energy above hull",
      kind=ConstraintKind.EVIDENCE,
      executable=False,
      unit="eV/atom",
      operators=[],
      source="deferred",
      comparability_scope="requires a separately verified corrected-energy surface",
      missingness="not released in index_v1",
      relaxable=False,
      scientific_note="Deferred from v1.",
    ),
  ]
  return _finalize_registry(entries, index_id=index_id)


def freeze_numeric_bounds(
  registry: PropertyRegistry,
  records: Iterable[NavigatorRecord],
) -> PropertyRegistry:
  """Freeze robust index-level bounds; never derive bounds from a query result pool."""
  record_list = list(records)
  entries = deepcopy(registry.entries)
  for entry in entries:
    if entry.bounds is None:
      continue
    values = [
      float(value)
      for record in record_list
      if (value := _record_value(record, entry.field)) is not None
      and isinstance(value, (int, float))
    ]
    if len(values) < 2:
      continue
    low, high = np.quantile(np.asarray(values, dtype=float), [0.005, 0.995], method="linear")
    if high > low:
      entry.bounds = (float(low), float(high))
  return _finalize_registry(entries, index_id=registry.index_id)


def _record_value(record: NavigatorRecord, field: str) -> object:
  if hasattr(record, field):
    return getattr(record, field)
  return record.properties.get(field)


def _numeric_operators() -> list[ConstraintOperator]:
  return [
    ConstraintOperator.EQ,
    ConstraintOperator.LT,
    ConstraintOperator.LTE,
    ConstraintOperator.GT,
    ConstraintOperator.GTE,
  ]


def _finalize_registry(entries: list[RegistryEntry], *, index_id: str) -> PropertyRegistry:
  body = {
    "version": REGISTRY_VERSION,
    "index_id": index_id,
    "entries": [entry.model_dump(mode="json") for entry in entries],
  }
  return PropertyRegistry(
    version=REGISTRY_VERSION,
    index_id=index_id,
    entries=entries,
    digest=canonical_digest(body),
  )
