-- Transparent screen for high volumetric stiffness at bounded density.
-- Ranks a restricted element pool by bulk modulus first, mass second.
-- Bulk modulus is stiffness under uniform compression, not strength:
-- it says nothing about yield, toughness, fatigue, or environment.
SELECT
  material_id,
  reduced_formula,
  functional,
  density,
  bulk_modulus,
  energy_above_hull
FROM lemat_bulk
WHERE list_has_all(['Ti', 'Al', 'Si', 'C', 'N', 'Zr', 'B'], elements)
  AND nelements <= 4
  AND nsites <= 80
  AND density <= 4.5
  AND energy_above_hull <= 0.05
ORDER BY bulk_modulus DESC, density ASC;
