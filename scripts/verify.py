"""Reproducible offline failure/recovery verification and evidence export."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from civicflow.pipeline import load
from contractwatch.core import drift, profile


def verify():
    rows = [json.loads(line) for line in (ROOT / "examples/requests.jsonl").read_text().splitlines()]
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / "warehouse.sqlite"
        initial, _ = load(rows, db)
        replay, _ = load(rows, db)
        correction, _ = load([dict(rows[1], status="Closed", closed_date="2025-01-01T15:00:00")], db)
        blocked, _ = load([dict(rows[0], closed_date="2020-01-01")], db)
        with sqlite3.connect(db) as connection:
            silver = connection.execute("SELECT count(*) FROM requests").fetchone()[0]
            gold = connection.execute("SELECT sum(request_count) FROM daily_service_metrics").fetchone()[0]
        assert replay["inserted"] == 0 and replay["unchanged"] == 3
        assert correction["updated"] == 1 and silver == gold == 3
        assert blocked["status"] == "blocked_quality_gate"
    drift_result = drift(profile(rows), profile([dict(rows[0], agency=None, unique_key=1)]))
    assert any(change["severity"] == "error" for change in drift_result)
    evidence = {
        "verification": "synthetic deterministic fixture; not real-data scale evidence",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "initial_inserted": initial["inserted"],
        "replay_inserted": replay["inserted"],
        "replay_unchanged": replay["unchanged"],
        "correction_updated": correction["updated"],
        "bad_batch_status": blocked["status"],
        "silver_rows": silver, "gold_rows_reconciled": gold,
        "drift_detected": drift_result,
    }
    output = ROOT / "evidence/offline-verification.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    verify()
