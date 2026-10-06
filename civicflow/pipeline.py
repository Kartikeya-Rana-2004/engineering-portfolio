import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contractwatch.core import check, timestamp

FIELDS = "unique_key,created_date,closed_date,agency,complaint_type,borough,status"
ENDPOINT = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
ROOT = Path(__file__).resolve().parents[1]


def get_json(url):
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "CivicFlow-Portfolio/1.0"})
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
        time.sleep(2 ** attempt)


def fetch(start, end, max_rows=20000, page_size=1000):
    """Bounded, ordered API extraction; not a change-data-capture feed."""
    start_dt, end_dt = timestamp(start), timestamp(end)
    if start_dt >= end_dt:
        raise ValueError("start must precede end")
    if not 1 <= page_size <= 5000 or max_rows < 1:
        raise ValueError("invalid extraction limits")
    start, end = start_dt.isoformat(), end_dt.isoformat()
    rows, offset = [], 0
    while len(rows) < max_rows:
        limit = min(page_size, max_rows - len(rows))
        query = urllib.parse.urlencode({
            "$select": FIELDS,
            "$where": f"created_date >= '{start}' AND created_date < '{end}'",
            "$order": "created_date ASC,unique_key ASC",
            "$limit": limit, "$offset": offset,
        })
        page = get_json(f"{ENDPOINT}?{query}")
        if not isinstance(page, list):
            raise ValueError("API did not return a record array")
        rows.extend(page)
        offset += len(page)
        if len(page) < limit:
            return rows, False
    # An extra record tells us whether this bounded extraction was truncated.
    query = urllib.parse.urlencode({"$select": "unique_key", "$where": f"created_date >= '{start}' AND created_date < '{end}'", "$order": "created_date ASC,unique_key ASC", "$limit": 1, "$offset": offset})
    return rows, bool(get_json(f"{ENDPOINT}?{query}"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
 unique_key TEXT PRIMARY KEY, created_date TEXT NOT NULL, closed_date TEXT,
 agency TEXT NOT NULL, complaint_type TEXT NOT NULL, borough TEXT NOT NULL,
 status TEXT NOT NULL, resolution_hours REAL, content_hash TEXT NOT NULL,
 last_run_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, completed_at TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 source_rows INTEGER NOT NULL, accepted INTEGER NOT NULL, quarantined INTEGER NOT NULL,
 inserted INTEGER NOT NULL, updated INTEGER NOT NULL, unchanged INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine (
 run_id TEXT NOT NULL, row_index INTEGER NOT NULL, errors TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(run_id,row_index)
);
CREATE VIEW IF NOT EXISTS daily_service_metrics AS
 SELECT substr(created_date,1,10) AS day, borough, agency, complaint_type,
 count(*) AS request_count,
 sum(CASE WHEN closed_date IS NOT NULL THEN 1 ELSE 0 END) AS closed_count,
 avg(resolution_hours) AS avg_resolution_hours
 FROM requests GROUP BY 1,2,3,4;
"""


def load(rows, db_path, max_reject_fraction=0.05):
    if not 0 <= max_reject_fraction <= 1:
        raise ValueError("reject threshold must be between 0 and 1")
    contract = json.loads((ROOT / "contracts/nyc311.json").read_text())
    accepted, rejected, reasons = check(rows, contract)
    run_id = uuid.uuid4().hex
    report = {"run_id": run_id, "source_rows": len(rows), "accepted": len(accepted), "quarantined": len(rejected), "reasons": reasons, "inserted": 0, "updated": 0, "unchanged": 0}
    # Gate before opening the warehouse: bad batches cannot partially alter silver.
    if rows and len(rejected) / len(rows) > max_reject_fraction:
        report["status"] = "blocked_quality_gate"
        return report, rejected
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.executescript(SCHEMA)
        connection.execute("BEGIN IMMEDIATE")
        for row in accepted:
            normalized = {field: row.get(field) or None for field in FIELDS.split(",")}
            normalized["created_date"] = timestamp(row["created_date"]).isoformat()
            if normalized["closed_date"]:
                normalized["closed_date"] = timestamp(normalized["closed_date"]).isoformat()
            digest = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
            existing = connection.execute("SELECT content_hash FROM requests WHERE unique_key=?", (row["unique_key"],)).fetchone()
            if existing and existing[0] == digest:
                report["unchanged"] += 1
                continue
            hours = None
            if normalized["closed_date"]:
                hours = (timestamp(normalized["closed_date"]) - timestamp(normalized["created_date"])).total_seconds() / 3600
            values = [normalized[field] for field in FIELDS.split(",")] + [hours, digest, run_id]
            connection.execute("""INSERT INTO requests VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(unique_key) DO UPDATE SET created_date=excluded.created_date,
                closed_date=excluded.closed_date,agency=excluded.agency,
                complaint_type=excluded.complaint_type,borough=excluded.borough,
                status=excluded.status,resolution_hours=excluded.resolution_hours,
                content_hash=excluded.content_hash,last_run_id=excluded.last_run_id""", values)
            report["updated" if existing else "inserted"] += 1
        for rejected_row in rejected:
            connection.execute("INSERT INTO quarantine VALUES (?,?,?,?)", (run_id, rejected_row["index"], json.dumps(rejected_row["errors"]), json.dumps(rejected_row["record"])))
        checksum = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        connection.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)", (run_id, datetime.now(timezone.utc).isoformat(), checksum, len(rows), len(accepted), len(rejected), report["inserted"], report["updated"], report["unchanged"]))
    report["status"] = "completed"
    return report, rejected


def main():
    parser = argparse.ArgumentParser(description="NYC 311 bronze/silver/gold pipeline")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Replay a JSONL batch")
    source.add_argument("--fetch", action="store_true")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2025-01-08")
    parser.add_argument("--max-rows", type=int, default=20000)
    parser.add_argument("--output", type=Path, default=Path("data"))
    parser.add_argument("--max-reject-fraction", type=float, default=0.05)
    args = parser.parse_args()
    if args.fetch:
        rows, truncated = fetch(args.start, args.end, args.max_rows)
    else:
        rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
        truncated = None
    args.output.mkdir(parents=True, exist_ok=True)
    run_folder = args.output / "bronze" / uuid.uuid4().hex
    run_folder.mkdir(parents=True)
    (run_folder / "records.jsonl").write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
    (run_folder / "manifest.json").write_text(json.dumps({"source": str(args.input) if args.input else ENDPOINT, "fetched_at": datetime.now(timezone.utc).isoformat(), "start": args.start if args.fetch else None, "end": args.end if args.fetch else None, "truncated": truncated, "rows": len(rows)}, indent=2))
    started = time.perf_counter()
    report, rejected = load(rows, args.output / "warehouse.sqlite", args.max_reject_fraction)
    report.update({"load_seconds": round(time.perf_counter() - started, 4), "truncated": truncated, "bronze_path": str(run_folder)})
    (run_folder / "quarantine.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rejected))
    (run_folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.output / "latest-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
