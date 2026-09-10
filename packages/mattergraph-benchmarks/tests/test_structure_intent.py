from __future__ import annotations

import pytest
from mattergraph_benchmarks.structure_intent import (
  BENCHMARK_LICENSE,
  HumanRequestPublicationRecord,
  StructureIntentMetrics,
  public_release_gate,
  require_publishable_requests,
  seal_benchmark_splits,
  sft_investigation_gate,
)


def test_sft_gate_uses_capability_and_safety_triggers() -> None:
  safe_but_inaccurate = StructureIntentMetrics(
    field_operator_unit_macro_f1=0.85,
    outcome_state_accuracy=0.89,
    material_correction_rate=0.01,
    unsupported_field_proposal_rate=0.0,
    semantic_misclassification_rate=0.0,
    actual_unsupported_field_execution_count=0,
  )
  decision = sft_investigation_gate(safe_but_inaccurate)
  assert decision.passed is False
  assert len(decision.reasons) == 2


def test_unsupported_execution_is_a_system_invariant() -> None:
  metrics = StructureIntentMetrics(0.99, 0.99, 0.0, 0.0, 0.0, 1)
  with pytest.raises(AssertionError, match="unsupported field executed"):
    sft_investigation_gate(metrics)
  assert public_release_gate(metrics).passed is False


def test_public_release_rates_are_strictly_below_one_percent() -> None:
  boundary = StructureIntentMetrics(0.95, 0.95, 0.02, 0.01, 0.01, 0)
  passing = StructureIntentMetrics(0.95, 0.95, 0.02, 0.009, 0.009, 0)
  assert public_release_gate(boundary).passed is False
  assert public_release_gate(passing).passed is True


def test_human_request_requires_complete_publication_contract() -> None:
  record = HumanRequestPublicationRecord(
    request_id="hr-001",
    text="Find a ternary oxide with fewer than 20 sites.",
    split="test_v1",
    consent_provenance_id="consent-public-4f9d",
    explicit_publication_permission=True,
    license=BENCHMARK_LICENSE,
    no_employer_confidential_information=True,
    no_personally_identifying_information=True,
    no_proprietary_information=True,
    no_controlled_unclassified_information=True,
    no_export_controlled_information=True,
    deidentified=True,
    publication_rights_unambiguous=True,
  )
  assert require_publishable_requests([record]) == [record]
  invalid = HumanRequestPublicationRecord(**{
    **record.__dict__,
    "request_id": "hr-002",
    "no_export_controlled_information": False,
  })
  with pytest.raises(ValueError, match="export-control screening"):
    require_publishable_requests([invalid])


def test_split_sealing_rejects_cross_split_overlap() -> None:
  empty = {"probe_v1": [], "train_v1": [], "dev_v1": [], "test_v1": []}
  case = {
    "text": "Find an oxide",
    "request_family": "element_filter",
    "chemical_family": "oxide",
    "source_record_ids": ["a"],
  }
  manifest = seal_benchmark_splits({**empty, "probe_v1": [case]})
  assert len(manifest["manifest_sha256"]) == 64
  with pytest.raises(ValueError, match="overlaps"):
    seal_benchmark_splits({**empty, "probe_v1": [case], "test_v1": [case]})
