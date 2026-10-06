-- Run in the database emitted by the stack, using its Athena workgroup.
-- Views avoid showing silver fragments from a batch without a completion marker.
CREATE OR REPLACE VIEW requests_committed AS
SELECT s.* FROM requests_silver s
JOIN batch_commits c ON s.batch_id = c.batch_id
WHERE c.status = 'completed';

-- Arrival-time ordering is not a substitute for upstream revision timestamps.
CREATE OR REPLACE VIEW requests_latest AS
SELECT unique_key, created_date, closed_date, agency, complaint_type, borough,
       status, resolution_hours, dt, batch_id, ingested_at
FROM (
  SELECT s.*, row_number() OVER (
    PARTITION BY unique_key ORDER BY from_iso8601_timestamp(ingested_at) DESC, batch_id DESC
  ) AS revision_rank
  FROM requests_committed s
)
WHERE revision_rank = 1;

-- Run separately from the CREATE statements; bound the partition range.
SELECT dt, borough, agency, count(*) AS requests,
       count(closed_date) AS with_closure_date,
       avg(resolution_hours) AS mean_closure_hours
FROM requests_latest
WHERE dt BETWEEN '2025-01-01' AND '2025-01-07'
GROUP BY dt, borough, agency
ORDER BY dt, requests DESC;

-- Reconciliation should hold per completed batch before cross-batch deduplication.
SELECT c.batch_id, c.accepted, count(s.unique_key) AS loaded_records
FROM batch_commits c
LEFT JOIN requests_silver s ON c.batch_id = s.batch_id
WHERE c.status = 'completed'
GROUP BY c.batch_id, c.accepted
HAVING c.accepted <> count(s.unique_key);
