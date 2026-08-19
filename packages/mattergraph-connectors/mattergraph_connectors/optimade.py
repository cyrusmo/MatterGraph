"""Read any OPTIMADE provider and normalize it to MatterGraph materials.

OPTIMADE is a common API across ~20 materials databases, so one client reaches COD, AFLOW,
OQMD, Materials Project and NOMAD without a per-source SDK. What it does *not* give you is
properties: the only REQUIRED field on a structure entry is ``structure_features``, and the
standard defines no band gap, formation energy, hull energy, modulus, or density. Provider
properties are namespaced by construction (``_oqmd_stability``).

So this connector yields structures and chemistry, plus two things that make the records
rankable rather than inert: a density derived from the cell, and a small per-provider map of
namespaced fields onto canonical property names.

Four upstream behaviours here were verified against the live COD and OQMD APIs and each one
silently breaks a naive implementation:

1. ``response_fields`` is mandatory. COD's default response omits ``cartesian_site_positions``,
   ``species``, ``species_at_sites`` and ``nsites``, so every record would arrive structureless.
2. ``links.next`` is a bare string on OQMD and a ``{"href": ...}`` object on COD. Both are legal
   JSON:API. Handling one shape stops pagination early against the other.
3. ``species[].name`` is *not* an element symbol — COD uses labels like ``"Ti1_2_555"``.
   Composition must be resolved through ``chemical_symbols``/``concentration``.
4. ``cartesian_site_positions`` is Cartesian; :class:`CrystalStructure` stores fractional
   coordinates. Nothing validates the difference, so getting it wrong yields a plausible
   structure with a badly wrong density.
"""

from __future__ import annotations

import warnings
from types import TracebackType
from typing import Any

import httpx
from mattergraph.schema.material import Material, MaterialProperty
from mattergraph.schema.property import PropertyMethod
from mattergraph.schema.structure import CrystalStructure
from pymatgen.core import Composition, Lattice, Structure

from mattergraph_connectors.base import (
  ConnectorQuery,
  apply_property_filter,
  coerce_query,
  connector_provenance,
)
from mattergraph_connectors.http_policy import (
  ConnectorHTTPPolicy,
  ResponseCache,
  request_with_policy,
)

SOURCE_NAME = "optimade"

# Structures endpoints, not index meta-databases. providers.optimade.org/providers.json serves
# the latter, which do not answer /v1/structures at all. base_url= overrides this for any
# provider not listed.
PROVIDERS: dict[str, str] = {
  "cod": "https://www.crystallography.net/cod/optimade",
  "oqmd": "https://oqmd.org/optimade",
  # AFLOW's structures endpoint is down, not merely fussy: /v1/info answers 200 but
  # /v1/structures and /v1/info/structures both return HTTP 500 for every query shape tried,
  # including a bare request with no parameters. There is no client-side workaround. Kept here
  # so it works the moment AFLOW repairs it; see docs/connectors.md.
  "aflow": "https://aflow.org/API/optimade",
  "mp": "https://optimade.materialsproject.org",
  "nmd": "https://nomad-lab.eu/prod/v1/optimade",
}

# Requested explicitly because non-REQUIRED fields are omitted unless asked for.
_RESPONSE_FIELDS = [
  "lattice_vectors",
  "cartesian_site_positions",
  "species",
  "species_at_sites",
  "nsites",
  "nperiodic_dimensions",
  "dimension_types",
  "structure_features",
  "chemical_formula_reduced",
  "elements",
]

# Namespaced provider fields that map onto canonical property names.
_PROVIDER_PROPERTIES: dict[str, dict[str, tuple[str, str | None, dict[str, Any]]]] = {
  "oqmd": {
    "_oqmd_band_gap": ("band_gap", "eV", {}),
    "_oqmd_delta_e": ("formation_energy_per_atom", "eV/atom", {}),
    # OQMD's "stability" is a hull *distance* and goes negative for phases below the current
    # hull; Materials Project's energy_above_hull is >= 0 by construction. Ranking both in one
    # column repeats the Voigt-vs-VRH mistake, so the convention is recorded and the value is
    # never clamped.
    "_oqmd_stability": (
      "energy_above_hull",
      "eV/atom",
      {"hull_convention": "oqmd_hull_distance"},
    ),
  },
}

# A cell this flat is a broken record, not a thin one. Lattice.volume takes abs(), so a
# near-zero or left-handed cell passes CrystalStructure validation and yields a density off by
# orders of magnitude.
_MIN_CELL_VOLUME = 1e-6


class OptimadeConnectorError(Exception):
  """Base exception for OPTIMADE connector failures."""


class OptimadeHTTPError(OptimadeConnectorError):
  """Raised when a provider cannot be reached or returns an HTTP error."""


class OptimadePayloadError(OptimadeConnectorError):
  """Raised when a response does not match the expected page shape."""


class OptimadeMappingError(OptimadeConnectorError):
  """Raised when an entry cannot be mapped into a MatterGraph material."""


class OptimadeConnector:
  """Read structures from any OPTIMADE provider."""

  source_name = SOURCE_NAME

  def __init__(
    self,
    provider: str = "cod",
    *,
    base_url: str | None = None,
    timeout: float = 30.0,
    client: httpx.Client | None = None,
    http_policy: ConnectorHTTPPolicy | None = None,
    cache: ResponseCache | None = None,
  ) -> None:
    if base_url is None:
      if provider not in PROVIDERS:
        known = ", ".join(sorted(PROVIDERS))
        msg = (
          f"unknown OPTIMADE provider {provider!r}; known providers: {known}. "
          "Pass base_url= to use any other OPTIMADE endpoint"
        )
        raise ValueError(msg)
      base_url = PROVIDERS[provider]
    self.provider = provider
    self.base_url = base_url.rstrip("/")
    self._owns_client = client is None
    self._client = client or httpx.Client(timeout=timeout, follow_redirects=True)
    self._http_policy = http_policy or ConnectorHTTPPolicy(timeout_seconds=timeout)
    self._cache = cache

  def __enter__(self) -> OptimadeConnector:
    return self

  def __exit__(
    self,
    exc_type: type[BaseException] | None,
    exc: BaseException | None,
    traceback: TracebackType | None,
  ) -> None:
    self.close()

  def close(self) -> None:
    if self._owns_client:
      self._client.close()

  @property
  def supported_properties(self) -> frozenset[str]:
    """Density is always derivable; canonical mappings vary by provider."""
    mapped = _PROVIDER_PROPERTIES.get(self.provider, {})
    return frozenset({"density"} | {name for name, _, _ in mapped.values()})

  def fetch(self, query: ConnectorQuery | None = None, **legacy: Any) -> list[Material]:
    q = coerce_query(query, legacy, source_name=SOURCE_NAME)
    return self._fetch(q)

  def _fetch(self, query: ConnectorQuery) -> list[Material]:
    if query.source_ids:
      msg = "OptimadeConnector cannot fetch by source_ids; filter by elements instead"
      raise ValueError(msg)

    out: list[Material] = []
    url: str | None = f"{self.base_url}/v1/structures"
    params: dict[str, Any] | None = {
      "page_limit": min(query.page_size, query.max_records),
      "response_fields": ",".join(_RESPONSE_FIELDS + self._provider_fields()),
    }
    filter_expr = _elements_filter(query.elements)
    if filter_expr:
      params["filter"] = filter_expr

    while url and len(out) < query.max_records:
      page = self._get(url, params)
      rows = page["data"]
      if not rows:
        break
      for row in rows:
        if len(out) >= query.max_records:
          break
        material = self._safe_row_to_material(row)
        if material is not None:
          out.append(material)
      url = _next_link(page)
      # The next link already carries filter and paging; re-sending params would duplicate them.
      params = None

    return apply_property_filter(
      out, query, supported=self.supported_properties, source_name=SOURCE_NAME
    )

  def _provider_fields(self) -> list[str]:
    return sorted(_PROVIDER_PROPERTIES.get(self.provider, {}))

  def _get(self, url: str, params: dict[str, Any] | None) -> dict[str, Any]:
    try:
      response = request_with_policy(
        self._client,
        "GET",
        url,
        params=params,
        policy=self._http_policy,
        cache=self._cache,
      )
      response.raise_for_status()
    except httpx.HTTPStatusError as exc:
      status = exc.response.status_code
      msg = f"OPTIMADE request to {self.provider} failed with HTTP {status}"
      raise OptimadeHTTPError(msg) from exc
    except httpx.RequestError as exc:
      msg = f"OPTIMADE request to {self.provider} failed: {exc}"
      raise OptimadeHTTPError(msg) from exc

    try:
      page = response.json()
    except ValueError as exc:
      msg = f"OPTIMADE provider {self.provider} returned invalid JSON"
      raise OptimadePayloadError(msg) from exc

    if not isinstance(page, dict):
      msg = f"OPTIMADE response from {self.provider} must be a JSON object"
      raise OptimadePayloadError(msg)
    if not isinstance(page.get("data"), list):
      msg = f"OPTIMADE response from {self.provider} must include a list under 'data'"
      raise OptimadePayloadError(msg)
    return page

  def _safe_row_to_material(self, row: Any) -> Material | None:
    try:
      return _row_to_material(row, provider=self.provider)
    except OptimadeMappingError as exc:
      warnings.warn(str(exc), RuntimeWarning, stacklevel=2)
      return None


def _elements_filter(elements: list[str] | None) -> str | None:
  if not elements:
    return None
  quoted = ",".join(f'"{element}"' for element in elements)
  return f"elements HAS ALL {quoted}"


def _next_link(page: dict[str, Any]) -> str | None:
  """Read ``links.next`` in either legal JSON:API shape.

  OQMD returns a bare URL string; COD returns ``{"href": ...}``. Treating only one as valid
  stops pagination after the first page against the other, with no error.
  """
  links = page.get("links")
  if not isinstance(links, dict):
    return None
  nxt = links.get("next")
  if isinstance(nxt, str):
    return nxt or None
  if isinstance(nxt, dict):
    href = nxt.get("href")
    return href if isinstance(href, str) and href else None
  return None


def _row_to_material(row: Any, *, provider: str) -> Material:
  if not isinstance(row, dict):
    msg = "Skipping OPTIMADE row: row must be an object"
    raise OptimadeMappingError(msg)

  entry_id = _clean_string(row.get("id"))
  if entry_id is None:
    msg = "Skipping OPTIMADE row: missing id"
    raise OptimadeMappingError(msg)

  attrs = row.get("attributes")
  if not isinstance(attrs, dict):
    msg = f"Skipping OPTIMADE row {entry_id}: missing attributes"
    raise OptimadeMappingError(msg)

  structure = _structure_from_attributes(attrs, entry_id=entry_id)
  dimensionality = _dimensionality(attrs)

  formula = _clean_string(attrs.get("chemical_formula_reduced"))
  if formula is None and structure is not None:
    # chemical_formula_reduced is null for every partially-occupied record, because the spec
    # requires integer proportions and COD reports things like "H0.572O2Ti0.858". Those are
    # ordinary crystallography records, not broken ones, so derive the formula from the cell
    # we just built rather than dropping them.
    formula = str(to_pymatgen_composition(structure).reduced_formula)
  if formula is None:
    # chemical_formula_anonymous ("A2B") is deliberately not a fallback: pymatgen parses A as a
    # DummySpecies, so it would not raise — it would write elements=['A0+','B'] onto the record.
    msg = f"Skipping OPTIMADE row {entry_id}: no chemical_formula_reduced and no usable structure"
    raise OptimadeMappingError(msg)

  properties: list[MaterialProperty] = []
  source = f"{SOURCE_NAME}:{provider}"
  density_note: str | None = None
  if structure is not None:
    if dimensionality is not None and dimensionality != 3:
      # A vacuum-padded slab's bulk density measures the author's padding, not the material.
      density_note = (
        f"density not derived: nperiodic_dimensions={dimensionality}, so the cell's bulk "
        "density is an artifact of vacuum padding"
      )
    else:
      properties.append(_derived_density(structure, source=source, source_id=entry_id))
  properties.extend(_provider_properties(attrs, provider=provider, source_id=entry_id))

  try:
    return Material(
      material_id=f"{provider}:{entry_id}",
      formula=formula,
      structure=structure,
      dimensionality=dimensionality,
      properties=properties,
      provenance=[
        connector_provenance(
          source,
          source_id=entry_id,
          method=PropertyMethod.UNKNOWN if not properties else PropertyMethod.DFT,
          notes=density_note or f"OPTIMADE structures entry from {provider}",
          parameters={"provider": provider, "nperiodic_dimensions": dimensionality},
        )
      ],
      source_id=entry_id,
      metadata={
        "source": source,
        "provider": provider,
        "entry_id": entry_id,
        "nsites": attrs.get("nsites"),
        "structure_features": attrs.get("structure_features"),
      },
    )
  except OptimadeMappingError:
    raise
  except Exception as exc:  # noqa: BLE001
    msg = f"Skipping OPTIMADE row {entry_id}: could not map material ({exc})"
    raise OptimadeMappingError(msg) from exc


def _structure_from_attributes(attrs: dict[str, Any], *, entry_id: str) -> CrystalStructure | None:
  """Build a :class:`CrystalStructure`, or ``None`` when the entry carries no usable cell.

  A missing cell is normal rather than exceptional: providers omit these fields unless asked,
  and some entries genuinely have no structure. Returning ``None`` keeps the record instead of
  dropping it.
  """
  features = attrs.get("structure_features") or []
  if isinstance(features, list) and "assemblies" in features:
    msg = f"Skipping OPTIMADE row {entry_id}: assemblies cannot be represented as a structure"
    raise OptimadeMappingError(msg)

  lattice = attrs.get("lattice_vectors")
  positions = attrs.get("cartesian_site_positions")
  species = attrs.get("species")
  species_at_sites = attrs.get("species_at_sites")
  if not (lattice and positions and species and species_at_sites):
    warnings.warn(
      f"OPTIMADE row {entry_id}: no structure (missing lattice or site data)",
      RuntimeWarning,
      stacklevel=3,
    )
    return None

  # lattice_vectors may carry nulls in a non-periodic direction, which is not a cell we can use.
  if any(component is None for vector in lattice for component in vector):
    warnings.warn(
      f"OPTIMADE row {entry_id}: no structure (lattice_vectors contain nulls)",
      RuntimeWarning,
      stacklevel=3,
    )
    return None

  try:
    cell = Lattice(lattice)
  except Exception as exc:  # noqa: BLE001
    msg = f"Skipping OPTIMADE row {entry_id}: unusable lattice_vectors ({exc})"
    raise OptimadeMappingError(msg) from exc

  if cell.volume < _MIN_CELL_VOLUME:
    msg = (
      f"Skipping OPTIMADE row {entry_id}: cell volume {cell.volume:.3g} A^3 is degenerate; "
      "any density derived from it would be meaningless"
    )
    raise OptimadeMappingError(msg)

  compositions = _site_compositions(species, species_at_sites, entry_id=entry_id)
  if len(compositions) != len(positions):
    msg = (
      f"Skipping OPTIMADE row {entry_id}: {len(compositions)} sites but "
      f"{len(positions)} cartesian_site_positions"
    )
    raise OptimadeMappingError(msg)

  try:
    # coords_are_cartesian=True is the whole point: OPTIMADE serves Cartesian positions and
    # CrystalStructure stores fractional ones. pymatgen does the inversion.
    structure = Structure(
      lattice=cell,
      species=compositions,
      coords=positions,
      coords_are_cartesian=True,
    )
    return CrystalStructure.from_pymatgen(structure)
  except Exception as exc:  # noqa: BLE001
    msg = f"Skipping OPTIMADE row {entry_id}: could not build structure ({exc})"
    raise OptimadeMappingError(msg) from exc


def _site_compositions(
  species: Any,
  species_at_sites: Any,
  *,
  entry_id: str,
) -> list[Composition]:
  """Resolve each site's composition through the ``species`` table.

  ``species_at_sites`` holds *names*, and a name need not be an element symbol — COD emits
  labels like ``"Ti1_2_555"``. Using those names directly as pymatgen species, which
  ``pymatgen.ext.optimade`` does as a shortcut, fails outright on COD.
  """
  if not isinstance(species, list) or not isinstance(species_at_sites, list):
    msg = f"Skipping OPTIMADE row {entry_id}: species and species_at_sites must be lists"
    raise OptimadeMappingError(msg)

  table: dict[str, dict[str, float]] = {}
  for entry in species:
    if not isinstance(entry, dict):
      continue
    name = _clean_string(entry.get("name"))
    symbols = entry.get("chemical_symbols")
    concentrations = entry.get("concentration")
    if name is None or not isinstance(symbols, list) or not isinstance(concentrations, list):
      continue
    if len(symbols) != len(concentrations):
      msg = (
        f"Skipping OPTIMADE row {entry_id}: species {name!r} has "
        f"{len(symbols)} symbols but {len(concentrations)} concentrations"
      )
      raise OptimadeMappingError(msg)
    occupancy: dict[str, float] = {}
    for symbol, concentration in zip(symbols, concentrations, strict=True):
      # "vacancy" and "X" are legal chemical_symbols but are the absence of an atom, so they
      # reduce the site's occupancy rather than contributing to it.
      if str(symbol) in {"vacancy", "X"}:
        continue
      try:
        value = float(concentration)
      except (TypeError, ValueError):
        continue
      if value > 0:
        occupancy[str(symbol)] = occupancy.get(str(symbol), 0.0) + value
    table[name] = occupancy

  compositions: list[Composition] = []
  for site_name in species_at_sites:
    occupancy = table.get(str(site_name))
    if occupancy is None:
      msg = f"Skipping OPTIMADE row {entry_id}: site species {site_name!r} not in species table"
      raise OptimadeMappingError(msg)
    if not occupancy:
      msg = f"Skipping OPTIMADE row {entry_id}: site species {site_name!r} is fully vacant"
      raise OptimadeMappingError(msg)
    try:
      compositions.append(Composition(occupancy))
    except Exception as exc:  # noqa: BLE001
      msg = f"Skipping OPTIMADE row {entry_id}: bad occupancy for {site_name!r} ({exc})"
      raise OptimadeMappingError(msg) from exc
  return compositions


def _dimensionality(attrs: dict[str, Any]) -> int | None:
  raw = attrs.get("nperiodic_dimensions")
  if isinstance(raw, bool) or not isinstance(raw, int):
    # Fall back to summing dimension_types, which carries the same information per axis.
    types = attrs.get("dimension_types")
    if isinstance(types, list) and all(isinstance(t, int) and t in (0, 1) for t in types):
      return sum(types)
    return None
  return raw if 0 <= raw <= 3 else None


def _derived_density(
  structure: CrystalStructure,
  *,
  source: str,
  source_id: str,
) -> MaterialProperty:
  from mattergraph.normalization.structures import to_structure

  return MaterialProperty(
    name="density",
    value=float(to_structure(structure).density),
    unit="g/cm^3",
    source=source,
    method=PropertyMethod.DERIVED,
    source_id=source_id,
    extra={"derived_from": "lattice_vectors + species_at_sites"},
  )


def _provider_properties(
  attrs: dict[str, Any],
  *,
  provider: str,
  source_id: str,
) -> list[MaterialProperty]:
  mapping = _PROVIDER_PROPERTIES.get(provider)
  if not mapping:
    return []
  out: list[MaterialProperty] = []
  for field, (name, unit, extra) in mapping.items():
    raw = attrs.get(field)
    if raw is None:
      continue
    try:
      value = float(raw)
    except (TypeError, ValueError):
      continue
    out.append(
      MaterialProperty(
        name=name,
        value=value,
        unit=unit,
        source=f"{SOURCE_NAME}:{provider}",
        method=PropertyMethod.DFT,
        source_id=source_id,
        extra={"optimade_field": field, **extra},
      )
    )
  return out


def to_pymatgen_composition(structure: CrystalStructure) -> Composition:
  """The cell's own composition, used when the provider reports no reduced formula."""
  from mattergraph.normalization.structures import to_structure

  return to_structure(structure).composition


def _clean_string(value: Any) -> str | None:
  if value is None:
    return None
  cleaned = str(value).strip()
  return cleaned or None


__all__ = [
  "PROVIDERS",
  "OptimadeConnector",
  "OptimadeConnectorError",
  "OptimadeHTTPError",
  "OptimadeMappingError",
  "OptimadePayloadError",
]
