import os
from pathlib import Path

import pytest
from mattergraph import MaterialStore

_ROOT = Path(__file__).resolve().parents[3]  # MatterGraph
_DEMO = _ROOT / "data" / "demo" / "materials_sample.jsonl"


@pytest.fixture(scope="module", autouse=True)
def _set_demo_data() -> None:
  os.environ["MATTERGRAPH_DEMO_DATA"] = str(_DEMO)
  from app.services import store_service

  store_service.reset_store(MaterialStore.from_jsonl(_DEMO))
