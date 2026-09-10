from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Literal

BENCHMARK_LICENSE = "CC-BY-4.0"


@dataclass(frozen=True)
class HumanRequestPublicationRecord:
  request_id: str
  text: str
  split: Literal["probe_v1", "dev_v1", "test_v1"]
  consent_provenance_id: str
  explicit_publication_permission: bool
  license: str
  no_employer_confidential_information: bool
  no_personally_identifying_information: bool
  no_proprietary_information: bool
  no_controlled_unclassified_information: bool
  no_export_controlled_information: bool
  deidentified: bool
  publication_rights_unambiguous: bool


@dataclass(frozen=True)
class StructureIntentMetrics:
  field_operator_unit_macro_f1: float
  outcome_state_accuracy: float
  material_correction_rate: float
  unsupported_field_proposal_rate: float
  semantic_misclassification_rate: float
  actual_unsupported_field_execution_count: int


@dataclass(frozen=True)
class GateDecision:
  passed: bool
  reasons: tuple[str, ...]


def validate_publication_record(record: HumanRequestPublicationRecord) -> list[str]:
  issues: list[str] = []
  if not record.request_id.strip() or not record.text.strip():
    issues.append("request_id and text are required")
  if not record.consent_provenance_id.strip():
    issues.append("non-identifying consent provenance identifier is required")
  if record.license != BENCHMARK_LICENSE:
    issues.append(f"human requests must be licensed {BENCHMARK_LICENSE}")
  checks = {
    "explicit publication permission": record.explicit_publication_permission,
    "employer-confidential screening": record.no_employer_confidential_information,
    "PII screening": record.no_personally_identifying_information,
    "proprietary-information screening": record.no_proprietary_information,
    "controlled-unclassified-information screening": record.no_controlled_unclassified_information,
    "export-control screening": record.no_export_controlled_information,
    "deidentification": record.deidentified,
    "unambiguous publication rights": record.publication_rights_unambiguous,
  }
  issues.extend(f"missing {label}" for label, passed in checks.items() if not passed)
  return issues


def require_publishable_requests(
  records: Iterable[HumanRequestPublicationRecord],
) -> list[HumanRequestPublicationRecord]:
  validated = list(records)
  failures = {
    record.request_id: validate_publication_record(record)
    for record in validated
    if validate_publication_record(record)
  }
  if failures:
    raise ValueError(f"human request publication contract failed: {failures}")
  return validated


def sft_investigation_gate(metrics: StructureIntentMetrics) -> GateDecision:
  reasons: list[str] = []
  if metrics.field_operator_unit_macro_f1 < 0.90:
    reasons.append("supported field/operator/unit macro-F1 below 0.90")
  if metrics.outcome_state_accuracy < 0.90:
    reasons.append("outcome-state accuracy below 0.90")
  if metrics.material_correction_rate > 0.02:
    reasons.append("scientifically material correction rate above 2%")
  if metrics.unsupported_field_proposal_rate > 0.01:
    reasons.append("unsupported-field proposal rate above 1%")
  if metrics.semantic_misclassification_rate > 0.01:
    reasons.append("semantic-misclassification rate above 1%")
  if metrics.actual_unsupported_field_execution_count:
    raise AssertionError("deterministic invariant violated: an unsupported field executed")
  return GateDecision(passed=not reasons, reasons=tuple(reasons))


def public_release_gate(metrics: StructureIntentMetrics) -> GateDecision:
  reasons: list[str] = []
  if metrics.actual_unsupported_field_execution_count:
    reasons.append("unsupported fields reached execution")
  if metrics.field_operator_unit_macro_f1 < 0.90:
    reasons.append("supported field/operator/unit macro-F1 below 0.90")
  if metrics.outcome_state_accuracy < 0.90:
    reasons.append("outcome-state accuracy below 0.90")
  if metrics.material_correction_rate > 0.02:
    reasons.append("scientifically material correction rate above 2%")
  if metrics.unsupported_field_proposal_rate >= 0.01:
    reasons.append("unsupported-field proposal rate is not below 1%")
  if metrics.semantic_misclassification_rate >= 0.01:
    reasons.append("semantic-misclassification rate is not below 1%")
  return GateDecision(passed=not reasons, reasons=tuple(reasons))


def seal_benchmark_splits(
  splits: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
  required = {"probe_v1", "train_v1", "dev_v1", "test_v1"}
  if set(splits) != required:
    raise ValueError(f"benchmark splits must be exactly {sorted(required)}")
  seen: dict[str, str] = {}
  manifests: dict[str, Any] = {}
  for split in sorted(splits):
    fingerprints: list[str] = []
    for item in splits[split]:
      fingerprint = _case_fingerprint(item)
      if fingerprint in seen:
        raise ValueError(
          f"benchmark case overlaps {seen[fingerprint]} and {split}: {fingerprint}"
        )
      seen[fingerprint] = split
      fingerprints.append(fingerprint)
    manifests[split] = {
      "count": len(fingerprints),
      "case_fingerprints": sorted(fingerprints),
    }
  body = {
    "schema_version": "mattergraph-structure-intent-benchmark-v1",
    "license": BENCHMARK_LICENSE,
    "splits": manifests,
  }
  body["manifest_sha256"] = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
  return body


def publication_record_dict(record: HumanRequestPublicationRecord) -> dict[str, Any]:
  """Return public metadata; contributor identity and private consent mapping are never included."""
  return asdict(record)


def _case_fingerprint(item: dict[str, Any]) -> str:
  family = item.get("request_family", "")
  chemistry = item.get("chemical_family", "")
  text = " ".join(str(item.get("text", "")).lower().split())
  source_ids = sorted(str(value) for value in item.get("source_record_ids", []))
  return hashlib.sha256(
    _canonical([family, chemistry, text, source_ids]).encode("utf-8")
  ).hexdigest()


def _canonical(value: Any) -> str:
  return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
