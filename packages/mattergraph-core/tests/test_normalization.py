import pytest

from mattergraph import MaterialProperty
from mattergraph.normalization import (
  canonical_property_name,
  normalize_density,
  normalize_energy,
  normalize_energy_eV,
  normalize_length,
  normalize_pressure,
  normalize_temperature,
  preferred_unit,
)


def test_property_name_aliases() -> None:
  assert canonical_property_name("e_hull") == "energy_above_hull"
  assert canonical_property_name("optb88vdw_bandgap") == "band_gap"
  assert preferred_unit("rho") == "g/cm^3"
  prop = MaterialProperty(name=" e_above_hull ", value=0.01, source="mp")
  assert prop.name == "energy_above_hull"


def test_unit_normalization_quantities() -> None:
  assert normalize_energy_eV(1.0, "Ry") == pytest.approx(13.6056980659)
  assert normalize_energy(96.485332123, "kJ/mol", per_atom=True).unit == "eV/atom"
  assert normalize_pressure(1000, "MPa").value == pytest.approx(1.0)
  assert normalize_density(1000, "kg/m^3").value == pytest.approx(1.0)
  assert normalize_length(1, "nm").value == pytest.approx(10.0)
  assert normalize_temperature(25, "C").value == pytest.approx(298.15)


def test_unsupported_units_raise() -> None:
  with pytest.raises(ValueError, match="Unsupported density unit"):
    normalize_density(1.0, "lb/ft^3")
