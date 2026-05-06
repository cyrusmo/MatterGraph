-- Transparent element and complexity screen for a lightweight engineering pool.
SELECT
  material_id,
  reduced_formula,
  functional,
  nelements,
  nsites,
  density,
  bulk_modulus,
  energy_above_hull
FROM lemat_bulk
WHERE list_has_all(['Ti', 'Al', 'Si', 'C', 'N'], elements)
  AND nelements <= 4
  AND nsites <= 80;
