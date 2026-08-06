import pytest

from mattergraph import Material, MaterialProperty, MaterialStore, Scorecard
from mattergraph.derived import (
  derive_elastic,
  derive_elastic_for,
  elastic_frame,
  with_derived_properties,
)

# Handbook values: bulk and shear moduli in GPa, then reference Young's modulus and
# Poisson's ratio to check the derivation against.
HANDBOOK = [
  ("Fe", 170.0, 82.0, 211.0, 0.29),
  ("Ti", 110.0, 44.0, 116.0, 0.32),
  ("Al", 72.0, 26.0, 70.0, 0.35),
]


@pytest.mark.parametrize(("label", "k", "g", "youngs", "poisson"), HANDBOOK)
def test_derivation_matches_handbook_values(
  label: str, k: float, g: float, youngs: float, poisson: float
) -> None:
  result = derive_elastic(k, g)
  assert result.youngs_modulus == pytest.approx(youngs, rel=0.01), label
  assert result.poisson_ratio == pytest.approx(poisson, abs=0.015), label


def test_pugh_and_poisson_are_a_monotone_map_of_each_other() -> None:
  """They are computed from the same K and G, so they cannot disagree.

  Presenting them as independent agreement checks would be false; this pins the
  relationship so nobody later "fixes" one of them into disagreement.
  """
  results = [derive_elastic(100.0, g) for g in (20.0, 40.0, 60.0, 80.0, 120.0, 160.0)]
  pughs = [r.pugh_ratio for r in results]
  poissons = [r.poisson_ratio for r in results]

  assert pughs == sorted(pughs)
  assert poissons == sorted(poissons, reverse=True)  # strictly opposite ordering


def test_specific_stiffness_barely_separates_structural_metals() -> None:
  """The result the docstring promises: E/rho is ~26 MN*m/kg for Al, Ti and Fe alike."""
  values = [
    derive_elastic(k, g, rho).specific_stiffness
    for (_, k, g, _, _), rho in zip(HANDBOOK, (7.874, 4.398, 2.699), strict=True)
  ]
  assert all(v is not None for v in values)
  assert max(values) - min(values) < 2.0  # type: ignore[type-var]
  assert all(24.0 < v < 28.0 for v in values)  # type: ignore[operator]


@pytest.mark.parametrize(
  ("k", "g"),
  [
    (-10.0, 80.0),  # negative K: E comes out negative and would rank as a real candidate
    (100.0, -5.0),
    (0.0, 26.0),  # K = 0 gives nu = -1 exactly
    (72.0, 0.0),  # G = 0 is the incompressible-fluid limit, nonphysical for a solid
    (float("nan"), 26.0),
  ],
)
def test_unstable_input_is_rejected_not_returned(k: float, g: float) -> None:
  with pytest.raises(ValueError, match="positive|finite"):
    derive_elastic(k, g)


def test_auxetic_input_warns_but_is_returned() -> None:
  """Negative Poisson ratios are physically real, just vanishingly rare among metals."""
  result = derive_elastic(100.0, 200.0)  # G > 1.5K
  assert result.poisson_ratio < 0
  assert any("auxetic" in w for w in result.warnings)


def test_near_incompressible_input_warns() -> None:
  result = derive_elastic(1000.0, 1.0)
  assert result.poisson_ratio > 0.48
  assert any("incompressible" in w for w in result.warnings)


def _material(mid: str, **props: tuple[float, str | None]) -> Material:
  return Material(
    material_id=mid,
    formula="Fe",
    properties=[
      MaterialProperty(name=name, value=value, unit=unit, source="t", method="dft")
      for name, (value, unit) in props.items()
    ],
  )


def test_missing_modulus_yields_none_never_an_imputed_value() -> None:
  only_bulk = _material("a", bulk_modulus=(170.0, "GPa"))
  assert derive_elastic_for(only_bulk) is None
  # The material is returned untouched rather than silently gaining derived properties.
  assert with_derived_properties(only_bulk) is only_bulk


def test_units_are_normalized_before_arithmetic() -> None:
  """A K in GPa against a G in MPa gives a Pugh ratio wrong by 1000x that still looks fine."""
  mixed = _material("a", bulk_modulus=(170.0, "GPa"), shear_modulus=(82_000.0, "MPa"))
  consistent = _material("b", bulk_modulus=(170.0, "GPa"), shear_modulus=(82.0, "GPa"))

  a, b = derive_elastic_for(mixed), derive_elastic_for(consistent)
  assert a is not None and b is not None
  assert a.youngs_modulus == pytest.approx(b.youngs_modulus)


def test_absent_unit_is_assumed_gpa_and_warned_about() -> None:
  material = _material("a", bulk_modulus=(170.0, None), shear_modulus=(82.0, None))
  result = derive_elastic_for(material)
  assert result is not None
  assert any("no unit" in w for w in result.warnings)


def test_mixed_averaging_schemes_warn() -> None:
  material = Material(
    material_id="a",
    formula="Fe",
    properties=[
      MaterialProperty(
        name="bulk_modulus", value=170.0, unit="GPa", source="mp", method="dft",
        extra={"averaging_scheme": "vrh"},
      ),
      MaterialProperty(
        name="shear_modulus", value=82.0, unit="GPa", source="jarvis", method="dft",
        extra={"averaging_scheme": "voigt"},
      ),
    ],
  )
  result = derive_elastic_for(material)
  assert result is not None
  assert any("averaging scheme" in w for w in result.warnings)


def test_method_degrades_when_inputs_disagree() -> None:
  chimera = Material(
    material_id="a",
    formula="Fe",
    properties=[
      MaterialProperty(name="bulk_modulus", value=170.0, unit="GPa", source="t", method="dft"),
      MaterialProperty(
        name="shear_modulus", value=82.0, unit="GPa", source="t", method="experimental"
      ),
    ],
  )
  result = derive_elastic_for(chimera)
  assert result is not None
  assert result.method.value == "unknown"


def test_derived_properties_are_rankable_by_scorecard() -> None:
  pool = [with_derived_properties(m) for m in MaterialStore.from_demo().materials]
  if not pool:
    pytest.skip("no demo data")

  scorecard = Scorecard(objectives={"youngs_modulus": "maximize"})
  report = scorecard.report(pool)
  assert report["coverage"]["youngs_modulus"] == len(pool)
  assert report["ignored_objectives"] == []

  ranked = scorecard.rank(pool)
  assert len(ranked) == len(pool)
  # Iron has the highest Young's modulus of the three demo metals.
  assert ranked.iloc[0]["material_id"] == "demo-fe-bcc-1"


def test_elastic_frame_omits_materials_without_both_moduli() -> None:
  pool = [
    _material("has-both", bulk_modulus=(170.0, "GPa"), shear_modulus=(82.0, "GPa")),
    _material("bulk-only", bulk_modulus=(110.0, "GPa")),
  ]
  frame = elastic_frame(pool)
  assert list(frame["material_id"]) == ["has-both"]
  assert frame.iloc[0]["method"] == "dft"
