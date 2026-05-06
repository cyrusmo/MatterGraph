-- Check whether a candidate pool mixes DFT functionals.
SELECT
  functional,
  COUNT(*) AS row_count
FROM lemat_bulk
GROUP BY functional
ORDER BY row_count DESC, functional;
