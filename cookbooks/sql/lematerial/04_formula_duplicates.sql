-- Repeated reduced formulas are not automatically duplicates.
-- This query highlights multiplicity so you can separate formula counts
-- from immutable-id or structure-fingerprint duplication.
SELECT
  reduced_formula,
  COUNT(*) AS row_count,
  COUNT(DISTINCT immutable_id) AS distinct_immutable_ids,
  COUNT(DISTINCT structure_fingerprint) AS distinct_structure_fingerprints
FROM lemat_bulk
GROUP BY reduced_formula
HAVING COUNT(*) > 1
ORDER BY row_count DESC, reduced_formula;
