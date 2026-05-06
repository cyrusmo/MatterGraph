-- Compare energy-like values only within compatible workflow slices.
SELECT
  reduced_formula,
  functional,
  COUNT(*) AS row_count,
  MIN(energy_per_site) AS min_energy_per_site,
  MAX(energy_per_site) AS max_energy_per_site
FROM lemat_bulk
WHERE energy_per_site IS NOT NULL
GROUP BY reduced_formula, functional
ORDER BY reduced_formula, functional;
