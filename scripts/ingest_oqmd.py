#!/usr/bin/env python3
"""Ingest OQMD records through its OPTIMADE endpoint.

There is no native OQMD SDK connector here. OQMD speaks OPTIMADE, so `OptimadeConnector`
reaches it with no extra dependency — and the same code reaches COD, AFLOW and ~18 others by
changing one argument.
"""

from mattergraph_connectors import ConnectorQuery, OptimadeConnector, OptimadeConnectorError


def main() -> None:
  query = ConnectorQuery(elements=["Ti", "O"], max_records=5)
  try:
    with OptimadeConnector(provider="oqmd") as connector:
      materials = connector.fetch(query)
  except OptimadeConnectorError as exc:
    print(f"OQMD request failed: {exc}")
    raise SystemExit(1) from exc

  print(f"OQMD returned {len(materials)} materials.")
  for material in materials:
    parts = [f"{material.material_id:22s}", f"{material.reduced_formula:10s}"]
    density = material.get_numeric("density")
    if density is not None:
      parts.append(f"density={density:6.3f} g/cm^3 (derived)")
    hull = material.get_numeric("energy_above_hull")
    if hull is not None:
      # OQMD reports hull distance, which is negative below the hull. See docs/connectors.md.
      parts.append(f"hull_distance={hull:+.4f} eV/atom")
    print("  " + "  ".join(parts))


if __name__ == "__main__":
  main()
