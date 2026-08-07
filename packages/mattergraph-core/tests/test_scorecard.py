import pytest
from mattergraph import Material, MaterialProperty, Scorecard


def _material(mid: str, **props: float) -> Material:
  return Material(
    material_id=mid,
    formula="H",
    properties=[
      MaterialProperty(name=name, value=value, source="t", method="dft")
      for name, value in props.items()
    ],
  )


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


def test_zero_spread_objective_cannot_depend_on_direction() -> None:
  """An objective every candidate scores identically on carries no information.

  It previously normalized to all-ones under ``minimize`` and all-zeros under
  ``maximize``, so the direction label alone could reorder candidates that had not
  changed.
  """
  pool = [_material("a", flat=5.0, real=1.0), _material("b", flat=5.0, real=2.0)]

  ranked = {
    direction: Scorecard(objectives={"flat": direction, "real": "maximize"}).rank(pool)
    for direction in ("minimize", "maximize")
  }
  assert list(ranked["minimize"]["material_id"]) == list(ranked["maximize"]["material_id"])
  assert list(ranked["minimize"]["score"]) == pytest.approx(list(ranked["maximize"]["score"]))

  # The flat column is reported as ignored rather than silently absorbed.
  report = Scorecard(objectives={"flat": "maximize", "real": "maximize"}).report(pool)
  assert report["degenerate_objectives"] == ["flat"]
  assert report["effective_objectives"] == ["real"]


def test_zero_coverage_objective_does_not_deflate_scores() -> None:
  """Adding an objective nobody has a value for must not change any score."""
  pool = [_material("a", real=1.0), _material("b", real=2.0)]

  without = Scorecard(objectives={"real": "maximize"}).rank(pool)
  with_empty = Scorecard(objectives={"real": "maximize", "absent": "maximize"}).rank(pool)

  assert list(with_empty["score"]) == pytest.approx(list(without["score"]))

  report = Scorecard(objectives={"real": "maximize", "absent": "maximize"}).report(pool)
  assert report["coverage"] == {"real": 2, "absent": 0}
  assert report["zero_coverage_objectives"] == ["absent"]


def test_missing_policy_controls_how_absent_values_score() -> None:
  """A candidate missing an objective is scored, not excluded — and the policy is explicit."""
  # `a` lacks `partial` entirely; `b` and `c` span it so the column is informative.
  pool = [
    _material("a", real=3.0),
    _material("b", real=2.0, partial=1.0),
    _material("c", real=1.0, partial=9.0),
  ]
  objectives: dict[str, str] = {"real": "maximize", "partial": "maximize"}

  worst = Scorecard(objectives=objectives, missing="worst").rank(pool)
  neutral = Scorecard(objectives=objectives, missing="neutral").rank(pool)
  excluded = Scorecard(objectives=objectives, missing="exclude").rank(pool)

  score_of = lambda df, mid: float(df.loc[df["material_id"] == mid, "score"].iloc[0])  # noqa: E731
  assert score_of(neutral, "a") > score_of(worst, "a")
  assert set(excluded["material_id"]) == {"b", "c"}
  assert "a" in set(worst["material_id"])

  assert Scorecard(objectives=objectives).report(pool)["missing_policy"] == "worst"
  with pytest.raises(ValueError, match="unsupported missing policy"):
    Scorecard(objectives=objectives, missing="bogus")  # type: ignore[arg-type]


def test_report_flags_binary_normalization_and_constraint_exclusions() -> None:
  pool = [
    _material("a", real=1.0),
    _material("b", real=2.0),
    _material("c", real=99.0),
  ]
  report = Scorecard(objectives={"real": "maximize"}, constraints={"real": {"max": 50.0}}).report(
    pool
  )
  assert report["pool_size"] == 3
  assert report["ranked_count"] == 2
  assert report["excluded_by_constraints"] == 1
  # Two survivors means min-max collapses every objective to {0, 1}.
  assert report["binary_normalization"] is True


# --- convention mixing --------------------------------------------------------------------
# A ranking column that pools two conventions changes a shortlist without changing any
# material, which is exactly what report() exists to surface.


def _with_hull(mid: str, value: float, extra: dict[str, object]) -> Material:
  return Material(
    material_id=mid,
    formula="TiO2",
    properties=[
      MaterialProperty(
        name="energy_above_hull", value=value, unit="eV/atom", source="test", extra=extra
      )
    ],
  )


def test_mixing_a_marked_and_an_unmarked_convention_is_flagged() -> None:
  """The real OQMD/MP case: OQMD marks its hull convention and MP marks nothing.

  Counting only non-null markers would see one distinct value here and report no mixing.
  """
  pool = [
    _with_hull("oqmd", -0.037, {"hull_convention": "oqmd_hull_distance"}),
    _with_hull("mp", 0.012, {}),
  ]
  report = Scorecard(objectives={"energy_above_hull": "minimize"}).report(pool)

  assert report["mixed_hull_conventions"] == {
    "energy_above_hull": ["oqmd_hull_distance", "unspecified"]
  }


def test_a_single_convention_is_not_flagged() -> None:
  pool = [
    _with_hull("a", 0.01, {"hull_convention": "oqmd_hull_distance"}),
    _with_hull("b", 0.02, {"hull_convention": "oqmd_hull_distance"}),
  ]
  report = Scorecard(objectives={"energy_above_hull": "minimize"}).report(pool)

  assert report["mixed_hull_conventions"] == {}


def test_an_entirely_unmarked_pool_is_not_flagged() -> None:
  """Every pre-OPTIMADE source is unmarked; that must not become a permanent warning."""
  pool = [_with_hull("a", 0.01, {}), _with_hull("b", 0.02, {})]
  report = Scorecard(objectives={"energy_above_hull": "minimize"}).report(pool)

  assert report["mixed_hull_conventions"] == {}


def _with_modulus(mid: str, value: float, extra: dict[str, object]) -> Material:
  return Material(
    material_id=mid,
    formula="TiO2",
    properties=[
      MaterialProperty(
        name="bulk_modulus", value=value, unit="GPa", source="test", extra=extra
      )
    ],
  )


def test_averaging_schemes_flag_a_marked_and_unmarked_mix_too() -> None:
  """Same latent bug as the hull case: an unlabelled source used to be skipped."""
  pool = [
    _with_modulus("mp", 100.0, {"averaging_scheme": "vrh"}),
    _with_modulus("csv", 120.0, {}),
  ]
  report = Scorecard(objectives={"bulk_modulus": "maximize"}).report(pool)

  assert report["mixed_averaging_schemes"] == {"bulk_modulus": ["unspecified", "vrh"]}


def test_averaging_schemes_still_flag_two_named_schemes() -> None:
  pool = [
    _with_modulus("mp", 100.0, {"averaging_scheme": "vrh"}),
    _with_modulus("jarvis", 120.0, {"averaging_scheme": "voigt"}),
  ]
  report = Scorecard(objectives={"bulk_modulus": "maximize"}).report(pool)

  assert report["mixed_averaging_schemes"] == {"bulk_modulus": ["voigt", "vrh"]}
