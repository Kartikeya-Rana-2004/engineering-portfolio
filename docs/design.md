# Design decisions

## Why dependency-free Python and SQLite?
The goal is executable evidence of correctness, not a cloud diagram that cannot be reproduced. Python's standard library covers the API client, validation, CLI, hashing, and tests. SQLite gives atomic transactions and indexed source keys. A warehouse adapter is a future extension, not an existing cloud capability.

## Why a content hash and a source key?
Source key uniqueness prevents replay duplicates. The normalized-content hash distinguishes unchanged records from source corrections. A source record has no published version in this extraction, so arrival order wins for changed records. Replaying an older batch can overwrite a newer correction. Real deployments need source version ordering, an update timestamp, or an explicit backfill reconciliation policy. This limitation is documented rather than hidden.

## Why no automatic checkpoint?
A creation-time watermark would skip later changes to existing requests. The CLI therefore takes explicit windows and preserves manifests. Incremental warehouse updates work; change-complete upstream ingestion is not claimed.

## Failure matrix

| Failure | Behavior | Recovery |
| --- | --- | --- |
| API 429/5xx or transient network problem | Bounded exponential retry; then fail | Re-run extraction |
| Permanent API 4xx | Fail without repeated retries | Correct query/permissions |
| Too many invalid records | Preserve bronze/rejections, block warehouse mutation | Inspect contract/source; replay after resolution |
| Crash/SQL failure during load | Warehouse transaction rolls back | Replay preserved bronze |
| Same records loaded again | Skip unchanged keys | No duplicate rows |
| Source correction | Update existing key | Gold view reflects correction |
| File/report export fails after database commit | Warehouse audit remains authoritative | Regenerate report; inspect run audit |

## Metrics semantics
`inserted`, `updated`, and `unchanged` count accepted record operations, not necessarily distinct keys within a source batch. Request counts in silver/gold count unique source keys. SHA-256 audit checksum represents canonical JSON batch content, not the exact downloaded response bytes. Local duration measures warehouse validation/loading only; it excludes network extraction and is not a service-level guarantee.
