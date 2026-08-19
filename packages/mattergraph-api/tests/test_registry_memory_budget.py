from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.memory_budget


@pytest.mark.skipif(
  os.environ.get("MATTERGRAPH_RUN_MEMORY_TEST") != "1"
  or importlib.util.find_spec("psutil") is None,
  reason="run once in the dedicated Python 3.12 memory-budget CI job",
)
def test_registry_peak_rss_stays_inside_public_workbench_budget() -> None:
  import psutil

  probe = Path(__file__).with_name("registry_memory_probe.py")
  child = subprocess.Popen(
    [sys.executable, str(probe)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
  )
  assert child.stdout is not None
  assert child.stdin is not None
  assert child.stdout.readline().strip() == "READY"
  process = psutil.Process(child.pid)
  baseline = process.memory_info().rss
  peak = baseline
  child.stdin.write("go\n")
  child.stdin.flush()

  while child.poll() is None:
    try:
      peak = max(peak, process.memory_info().rss)
    except psutil.NoSuchProcess:
      break
    time.sleep(0.01)

  stdout, stderr = child.communicate(timeout=5)
  assert child.returncode == 0, stderr
  result = json.loads(stdout.strip().splitlines()[-1])
  assert result["import_count"] == 8
  assert result["evicted_count"] >= 1
  assert result["stats"]["normalized_bytes"] <= 32 * 1024 * 1024
  assert peak < 250 * 1024 * 1024
  assert peak - baseline < 140 * 1024 * 1024
