# ContractWatch: data contracts and drift gates

Independent module with a JSONL CLI. CivicFlow consumes the same validation engine before changing its warehouse.

```bash
python3 -m contractwatch examples/requests.jsonl --contract contracts/nyc311.json --output data/good-report.json
python3 -m contractwatch examples/bad-requests.jsonl --contract contracts/nyc311.json --output data/bad-report.json
```

The second command intentionally exits 1. Inspect the report for invalid timestamps, type changes, unknown columns, and inconsistent temporal relationships. Raw rejected payloads are available through the library API; the CLI report contains counts/reasons rather than payloads.

Contracts support `string`, `number`, `integer`, and ISO timestamp values; required fields; optional enums and numeric bounds; allow/reject unknown fields; and `gte` comparisons between timestamps. No automatic type coercion is performed. Malformed JSONL/configuration exits with an error rather than being treated as an accepted record.

## Sampled drift comparison

Create a baseline observed profile:

```bash
python3 -c 'import json; from pathlib import Path; r=json.loads(Path("data/good-report.json").read_text()); Path("data/baseline.json").write_text(json.dumps(r["profile"]))'
python3 -m contractwatch examples/bad-requests.jsonl --contract contracts/nyc311.json --baseline data/baseline.json
```

Removed fields and changed observed types are errors; added fields are warnings; missingness increases above the configured tolerance are errors. The contract may independently reject added fields. `--null-tolerance 0.1` means an increase of more than 10 percentage points, not a relative 10% increase. Missingness here counts missing keys and JSON nulls; empty strings are handled by required-field validation.

This tool reports structural/sample drift, not distribution drift or model-performance drift. It loads the input batch in memory; it is designed for bounded batches rather than unbounded streams.
