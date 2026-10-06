# CivicFlow: correction-aware public-data pipeline

## Scenario
An operations team wants daily request counts and closure-time summaries from NYC 311. Source records can change after initial creation. A naive append job duplicates requests on replay; a naive overwrite can erase good data when an upstream batch fails.

## Implemented
1. Fetch a date window with selected fields, an explicit two-column sort, a row cap, and retry/backoff for transient errors.
2. Save every downloaded/replayed batch and a manifest before warehouse loading.
3. Check required fields, types, timestamps, unknown fields, and closure-after-creation consistency using ContractWatch.
4. Block excessive rejects before opening the warehouse; retain rejection evidence in bronze.
5. Within a transaction, compare SHA-256 normalized content hashes, insert new keys, update corrected keys, and skip unchanged records.
6. Persist rejected rows and a run audit in the same warehouse transaction.
7. Expose daily request/closure counts and average closure hours through a SQL view; export an offline HTML dashboard.

## Recovery commands

Replay a failed or interrupted download batch after inspecting/fixing the cause:

```bash
python3 -m civicflow --input data/bronze/BATCH_ID/records.jsonl
```

Re-fetch a historical date window to pick up corrections for that window. Do not assume a creation-date window captures all source updates. A strict contract change should be reviewed and versioned rather than silently accepted.

If loading fails after bronze is written, the bronze batch remains available. The warehouse transaction rolls back; the process exits with an error. Filesystem/report publication and the warehouse transaction are not a single distributed transaction; the database audit is authoritative for successful loads.

## Next extensions, not current capabilities
PostgreSQL/warehouse adapter, source-update checkpoint if a reliable upstream change field becomes available, scheduled orchestration, S3 storage, dbt models, and multi-worker coordination. No AWS deployment is claimed.
