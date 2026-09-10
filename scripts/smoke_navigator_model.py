from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MODEL = "Qwen/Qwen3-4B"
REVISION = "1cfa9a7208912126459214e8b04321603b3df60c"
EXPECTED = {
  "transformers": "4.52.4",
  "trl": "0.18.2",
  "peft": "0.15.2",
  "outlines": "1.0.3",
}
SYSTEM_PROMPT = """You compile materials requests into a proposed constraint plan.
Use only these executable fields: formula, elements, nelements, nsites, density,
absolute_total_magnetization, absolute_total_magnetization_per_site,
maximum_absolute_reported_site_moment, maximum_force_norm, functional, cross_compatibility.
Never map an unsupported scientific concept onto a supported field. Put unsupported or ambiguous
requirements in unresolved_requirements. Do not confirm constraints and do not execute them.
"""


class SmokeConstraint(BaseModel):
  model_config = ConfigDict(extra="forbid")

  field: str
  operator: Literal["eq", "lt", "lte", "gt", "gte", "include_all", "exclude_any"]
  value: float | int | str | bool | list[str]
  unit: str | None = None
  label: str


class SmokeUnresolved(BaseModel):
  model_config = ConfigDict(extra="forbid")

  text: str
  reason: str


class SmokeProposal(BaseModel):
  model_config = ConfigDict(extra="forbid")

  constraints: list[SmokeConstraint] = Field(default_factory=list)
  unresolved_requirements: list[SmokeUnresolved] = Field(default_factory=list)


def main() -> None:
  parser = argparse.ArgumentParser(description="Qualify the frozen navigator model environment.")
  parser.add_argument("--output", type=Path)
  parser.add_argument(
    "--compare-manifest",
    type=Path,
    help="First clean-run manifest; required before status can become qualified.",
  )
  args = parser.parse_args()
  versions = {name: importlib.metadata.version(name) for name in EXPECTED}
  mismatches = {
    name: {"expected": EXPECTED[name], "actual": actual}
    for name, actual in versions.items()
    if actual != EXPECTED[name]
  }
  if mismatches:
    raise RuntimeError(f"pinned package mismatch: {mismatches}")

  import outlines
  from huggingface_hub import hf_hub_download
  from transformers import AutoModelForCausalLM, AutoTokenizer

  tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=REVISION)
  model = AutoModelForCausalLM.from_pretrained(MODEL, revision=REVISION, device_map="auto")
  constrained_model = outlines.from_transformers(model, tokenizer)
  fixtures = [
    "Find a cobalt-free ternary oxide with fewer than 20 sites.",
    "Require SCAN and corrosion resistance.",
  ]
  outputs = [_generate(constrained_model, tokenizer, text) for text in fixtures]
  repeated = [_generate(constrained_model, tokenizer, text) for text in fixtures]
  if outputs != repeated:
    raise RuntimeError("deterministic fixture outputs differed across repeated runs")
  fixture_hash = hashlib.sha256(
    json.dumps(outputs, sort_keys=True).encode("utf-8")
  ).hexdigest()
  clean_run_comparison = "pending_second_clean_run"
  if args.compare_manifest:
    previous = json.loads(args.compare_manifest.read_text(encoding="utf-8"))
    if previous.get("fixture_output_sha256") != fixture_hash:
      raise RuntimeError("fixture outputs differ from the first clean-run manifest")
    clean_run_comparison = "matched_first_clean_run"
  result: dict[str, Any] = {
    "status": "qualified" if args.compare_manifest else "first_clean_run_complete",
    "model": MODEL,
    "revision": REVISION,
    "versions": versions,
    "enable_thinking": False,
    "generation": {
      "do_sample": False,
      "num_beams": 1,
      "num_return_sequences": 1,
      "max_new_tokens": 512,
      "temperature": "unset",
      "top_p": "unset",
      "top_k": "unset",
    },
    "system_prompt_sha256": _digest(SYSTEM_PROMPT),
    "output_schema_sha256": _digest(_canonical_json(SmokeProposal.model_json_schema())),
    "environment_lock_sha256": _digest(_canonical_json(versions)),
    "chat_template_sha256": _digest(str(tokenizer.chat_template)),
    "tokenizer_file_sha256": _tokenizer_hashes(hf_hub_download),
    "fixture_output_sha256": fixture_hash,
    "clean_run_comparison": clean_run_comparison,
  }
  serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
  if args.output:
    args.output.write_text(serialized, encoding="utf-8")
  else:
    print(serialized, end="")


def _generate(model: Any, tokenizer: Any, text: str) -> dict[str, Any]:
  prompt = tokenizer.apply_chat_template(
    [
      {"role": "system", "content": SYSTEM_PROMPT},
      {"role": "user", "content": text},
    ],
    tokenize=False,
    add_generation_prompt=True,
    enable_thinking=False,
  )
  generated = model(
    prompt,
    output_type=SmokeProposal,
    do_sample=False,
    num_beams=1,
    num_return_sequences=1,
    max_new_tokens=512,
  )
  proposal = SmokeProposal.model_validate_json(generated)
  return proposal.model_dump(mode="json")


def _tokenizer_hashes(download: Any) -> dict[str, str]:
  hashes: dict[str, str] = {}
  for filename in (
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.json",
    "merges.txt",
  ):
    try:
      path = Path(download(repo_id=MODEL, filename=filename, revision=REVISION))
    except Exception:  # pragma: no cover - a pinned tokenizer need not expose every format
      continue
    hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
  if not hashes:
    raise RuntimeError("no tokenizer files were resolved from the frozen model revision")
  return hashes


def _canonical_json(value: Any) -> str:
  return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: str) -> str:
  return hashlib.sha256(value.encode("utf-8")).hexdigest()


if __name__ == "__main__":
  main()
