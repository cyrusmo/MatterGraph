from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from mattergraph.navigator.index import freeze_index


def main() -> None:
  parser = argparse.ArgumentParser(
    description="Build the deterministic MatterGraph navigator index from pinned source files."
  )
  parser.add_argument("inputs", nargs="+", type=Path)
  parser.add_argument("--output", required=True, type=Path)
  parser.add_argument("--manifest", required=True, type=Path)
  parser.add_argument("--target-count", type=int, default=25_000)
  args = parser.parse_args()

  records: list[dict[str, Any]] = []
  source_hashes: dict[str, str] = {}
  for path in args.inputs:
    raw = path.read_bytes()
    source_key = path.name
    if source_key in source_hashes:
      raise ValueError(f"source basenames must be unique for a canonical manifest: {source_key}")
    source_hashes[source_key] = hashlib.sha256(raw).hexdigest()
    records.extend(_load(path, raw))
  frozen = freeze_index(records, target_count=args.target_count, source_hashes=source_hashes)
  args.output.parent.mkdir(parents=True, exist_ok=True)
  args.manifest.parent.mkdir(parents=True, exist_ok=True)
  with args.output.open("w", encoding="utf-8") as output:
    for record in frozen.records:
      output.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
      output.write("\n")
  args.manifest.write_text(
    json.dumps(frozen.manifest, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
  )


def _load(path: Path, raw: bytes) -> list[dict[str, Any]]:
  suffix = path.suffix.lower()
  if suffix == ".jsonl":
    return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
  if suffix == ".json":
    value = json.loads(raw)
    if isinstance(value, dict):
      value = value.get("records")
    if not isinstance(value, list):
      raise ValueError(f"{path} must contain a JSON array or records array")
    return [dict(item) for item in value]
  if suffix == ".parquet":
    try:
      import pandas as pd
    except ImportError as exc:
      raise ImportError("Parquet input requires pandas and pyarrow or fastparquet") from exc
    return [
      {key: _jsonable(value) for key, value in record.items()}
      for record in pd.read_parquet(path).to_dict(orient="records")
    ]
  raise ValueError(f"unsupported input format: {path}")


def _jsonable(value: Any) -> Any:
  if isinstance(value, dict):
    return {str(key): _jsonable(item) for key, item in value.items()}
  if isinstance(value, (list, tuple)):
    return [_jsonable(item) for item in value]
  if hasattr(value, "tolist"):
    return _jsonable(value.tolist())
  if isinstance(value, float) and not math.isfinite(value):
    return None
  return value


if __name__ == "__main__":
  main()
