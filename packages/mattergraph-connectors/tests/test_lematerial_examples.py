from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_lematerial_examples_run() -> None:
  root = Path(__file__).resolve().parents[3]
  examples = [
    root / "examples" / "lematerial" / "01_schema_report.py",
    root / "examples" / "lematerial" / "02_candidate_slice_report.py",
    root / "examples" / "lematerial" / "03_graph_export.py",
  ]

  for example in examples:
    completed = subprocess.run(
      [sys.executable, str(example)],
      cwd=root,
      check=True,
      capture_output=True,
      text=True,
    )
    assert completed.stdout.strip()
