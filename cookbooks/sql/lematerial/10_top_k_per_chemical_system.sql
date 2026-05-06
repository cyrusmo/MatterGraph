-- Keep only the top-k records per chemical system after a transparent score.
WITH ranked AS (
  SELECT
    *,
    ROW_NUMBER() OVER (
      PARTITION BY reduced_formula
      ORDER BY bulk_modulus DESC NULLS LAST, energy_above_hull ASC NULLS LAST
    ) AS rk
  FROM lemat_bulk
)
SELECT
  material_id,
  reduced_formula,
  functional,
  bulk_modulus,
  energy_above_hull
FROM ranked
WHERE rk <= 3
ORDER BY reduced_formula, rk;
