from mattergraph import Material, MaterialProperty, Scorecard


def test_scorecard_min_max_and_constraints() -> None:
  a = Material(
    material_id="a",
    formula="H",
    properties=[
      MaterialProperty(name="y", value=1.0, source="t", method="dft"),
      MaterialProperty(name="x", value=10.0, source="t", method="dft"),
    ],
  )
  b = Material(
    material_id="b",
    formula="H",
    properties=[
      MaterialProperty(name="y", value=0.0, source="t", method="dft"),
      MaterialProperty(name="x", value=0.0, source="t", method="dft"),
    ],
  )
  c = Material(
    material_id="c",
    formula="H",
    properties=[
      MaterialProperty(name="y", value=0.5, source="t", method="dft"),
      MaterialProperty(name="x", value=2.0, source="t", method="dft"),
    ],
  )
  sc = Scorecard(
    objectives={"x": "maximize", "y": "minimize"},
    constraints={"x": {"max": 5.0}},
  )
  df = sc.rank([a, b, c])
  assert set(df["material_id"]) == {"b", "c"}  # a fails x max
  top = df.iloc[0]["material_id"]
  assert top in {"b", "c"}
