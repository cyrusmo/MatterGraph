-- Surface force-quality indicators before using trajectory-derived values.
SELECT
  material_id,
  reduced_formula,
  max_force,
  force_quality_flag
FROM lemat_bulk
WHERE max_force IS NOT NULL
ORDER BY max_force DESC
LIMIT 100;
