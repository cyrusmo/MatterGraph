from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path


def main() -> None:
  parser = argparse.ArgumentParser(
    description="Publish the reproducible MatterGraph Grounded Explorer Docker Space."
  )
  parser.add_argument("--repo-id", default="cyrusmo/MatterGraph-Grounded-Explorer")
  parser.add_argument("--index", required=True, type=Path)
  parser.add_argument("--manifest", required=True, type=Path)
  parser.add_argument("--confirm-publish", action="store_true")
  args = parser.parse_args()
  if not args.confirm_publish:
    raise SystemExit("Refusing external publication without --confirm-publish")
  token = os.environ.get("HF_TOKEN")
  if not token:
    raise SystemExit("HF_TOKEN is required and is never printed or written")
  manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
  if manifest.get("index_id") != "index_v1" or manifest.get("target_count") != 25_000:
    raise SystemExit("manifest must identify the frozen 25,000-record index_v1")
  if sum(1 for line in args.index.open(encoding="utf-8") if line.strip()) != 25_000:
    raise SystemExit("index JSONL must contain exactly 25,000 non-empty records")
  try:
    from huggingface_hub import HfApi
  except ImportError as exc:
    raise SystemExit("Install huggingface_hub to publish the Space") from exc

  root = Path(__file__).resolve().parents[1]
  with tempfile.TemporaryDirectory(prefix="mattergraph-hf-space-") as temporary:
    staging = Path(temporary)
    for relative in ["packages", "apps/web", "data/demo"]:
      shutil.copytree(root / relative, staging / relative)
    (staging / "data" / "navigator").mkdir(parents=True)
    shutil.copy2(args.index, staging / "data" / "navigator" / "index_v1.jsonl")
    shutil.copy2(args.manifest, staging / "data" / "navigator" / "index_v1.manifest.json")
    shutil.copy2(root / "deploy/huggingface/Dockerfile", staging / "Dockerfile")
    shutil.copy2(root / "deploy/huggingface/README.md", staging / "README.md")
    shutil.copy2(root / "LICENSE", staging / "LICENSE")
    api = HfApi(token=token)
    api.create_repo(
      repo_id=args.repo_id,
      repo_type="space",
      space_sdk="docker",
      exist_ok=True,
      private=False,
    )
    api.upload_folder(
      repo_id=args.repo_id,
      repo_type="space",
      folder_path=staging,
      commit_message="Publish frozen MatterGraph Grounded Explorer",
      ignore_patterns=["**/node_modules/**", "**/dist/**", "**/__pycache__/**"],
    )
  print(f"Published https://huggingface.co/spaces/{args.repo_id}")
