-- Inspect available columns and basic row counts before filtering.
DESCRIBE SELECT * FROM lemat_bulk;

SELECT
  COUNT(*) AS row_count,
  COUNT(DISTINCT material_id) AS distinct_material_ids
FROM lemat_bulk;
