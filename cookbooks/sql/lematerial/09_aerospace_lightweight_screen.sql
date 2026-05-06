-- Lightweight structural candidate screen for transparent aerospace studies.
SELECT
  material_id,
  reduced_formula,
  functional,
  density,
  bulk_modulus,
  energy_above_hull
FROM lemat_bulk
WHERE list_has_all(['Ti', 'Al', 'Si', 'C', 'N'], elements)
  AND density <= 5.0
  AND energy_above_hull <= 0.05
ORDER BY density ASC, bulk_modulus DESC;
