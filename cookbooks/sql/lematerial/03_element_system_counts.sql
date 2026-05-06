-- Count how often each element appears across records.
WITH exploded AS (
  SELECT
    material_id,
    UNNEST(elements) AS element
  FROM lemat_bulk
)
SELECT
  element,
  COUNT(DISTINCT material_id) AS material_count
FROM exploded
GROUP BY element
ORDER BY material_count DESC, element;
