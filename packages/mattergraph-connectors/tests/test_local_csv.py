from pathlib import Path

from mattergraph_connectors import load_materials_from_csv


def test_load_materials_from_csv_demo() -> None:
  root = Path(__file__).resolve().parents[3]
  csv_path = root / "data" / "demo" / "properties_sample.csv"
  mats = load_materials_from_csv(csv_path)
  assert len(mats) == 3
  assert mats[0].material_id
  assert mats[0].formula
