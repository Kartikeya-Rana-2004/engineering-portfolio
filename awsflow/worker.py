"""SQS/EventBridge worker; deterministic S3 outputs and commit-last visibility."""
from collections import defaultdict
from datetime import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
from contractwatch.core import check, timestamp

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "contracts/nyc311.json").read_text())
FIELDS = tuple(CONTRACT["fields"])


def encode_jsonl(rows):
    return "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows).encode()


def transform(raw, batch_id, event_time, max_reject_fraction=0.05, max_rows=20000):
    if not 0 <= max_reject_fraction <= 1:
        raise ValueError("invalid rejection threshold")
    timestamp(event_time)
    lines = [line for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(lines) > max_rows:
        raise ValueError("row cap exceeded")
    rows, parse_errors = [], []
    for index, line in enumerate(lines):
        try:
            rows.append((index, json.loads(line)))
        except json.JSONDecodeError:
            parse_errors.append({"index": index, "errors": ["record:invalid_json"]})
    valid, invalid, reasons = check([row for _, row in rows], CONTRACT)
    for rejected in invalid:
        rejected["index"] = rows[rejected["index"]][0]
    rejected = parse_errors + invalid
    if parse_errors:
        reasons["record:invalid_json"] = len(parse_errors)
    status = "completed" if not lines or len(rejected) / len(lines) <= max_reject_fraction else "blocked_quality_gate"
    partitions = defaultdict(list)
    if status == "completed":
        for row in valid:
            normalized = {field: row.get(field) or None for field in FIELDS}
            created = timestamp(normalized["created_date"])
            normalized["created_date"] = created.isoformat()
            hours = None
            if normalized["closed_date"]:
                closed = timestamp(normalized["closed_date"])
                normalized["closed_date"] = closed.isoformat()
                hours = (closed - created).total_seconds() / 3600
            normalized.update(batch_id=batch_id, ingested_at=event_time, resolution_hours=hours)
            partitions[created.date().isoformat()].append(normalized)
    summary = {"batch_id": batch_id, "ingested_at": event_time, "status": status,
               "source_rows": len(lines), "accepted": len(valid), "rejected": len(rejected),
               "reasons": reasons, "partitions": sorted(partitions)}
    return dict(partitions), rejected, summary


def process_event(event, s3, expected_bucket, max_bytes=8 * 1024 * 1024):
    if event.get("source") != "aws.s3" or event.get("detail-type") != "Object Created":
        raise ValueError("unsupported event")
    detail = event["detail"]
    bucket, source = detail["bucket"]["name"], detail["object"]
    key, version = source["key"], source.get("version-id")
    if bucket != expected_bucket or not key.startswith("bronze/") or not key.endswith(".jsonl"):
        raise ValueError("event outside allowed input scope")
    if not version or version == "null":
        raise ValueError("versioned input required")
    event_time = event["time"]
    timestamp(event_time)
    response = s3.get_object(Bucket=bucket, Key=key, VersionId=version)
    if response["ContentLength"] > max_bytes:
        raise ValueError("byte cap exceeded")
    body = response["Body"]
    try:
        raw = body.read(max_bytes + 1)
    finally:
        body.close()
    if len(raw) > max_bytes:
        raise ValueError("byte cap exceeded")
    identity = json.dumps([bucket, key, version, hashlib.sha256(raw).hexdigest()])
    batch_id = hashlib.sha256(identity.encode()).hexdigest()
    partitions, rejected, summary = transform(raw, batch_id, event_time)
    summary.update(source_key=key, source_version=version, source_sha256=hashlib.sha256(raw).hexdigest())

    def put(target, payload, content_type="application/json", encoding=None):
        args = {"Bucket": bucket, "Key": target, "Body": payload,
                "ContentType": content_type, "ServerSideEncryption": "AES256"}
        if encoding:
            args["ContentEncoding"] = encoding
        s3.put_object(**args)

    if rejected:
        put(f"quarantine/{batch_id}.jsonl", encode_jsonl(rejected), "application/x-ndjson")
    # gzip mtime=0 makes a duplicate delivery write the same object bytes.
    for day, records in sorted(partitions.items()):
        put(f"silver/dt={day}/{batch_id}.jsonl.gz", gzip.compress(encode_jsonl(records), mtime=0), "application/x-ndjson", "gzip")
    put(f"audit/{batch_id}.json", json.dumps(summary, sort_keys=True).encode())
    if summary["status"] == "completed":
        # Commit is last. Athena queries must join silver to this manifest table.
        commit = {k: summary[k] for k in ("batch_id", "ingested_at", "status", "source_rows", "accepted", "rejected")}
        put(f"commits/{batch_id}.json", encode_jsonl([commit]))
    print(json.dumps({"kind": "awsflow_batch", **summary}))
    return summary


def handle(event, s3, expected_bucket, max_bytes=8 * 1024 * 1024):
    failures = []
    for message in event["Records"]:
        try:
            process_event(json.loads(message["body"]), s3, expected_bucket, max_bytes)
        except Exception as exc:
            # No raw payloads, exception text, or request data in logs.
            print(json.dumps({"kind": "awsflow_failure", "message_id": message["messageId"], "error_type": type(exc).__name__}))
            failures.append({"itemIdentifier": message["messageId"]})
    return {"batchItemFailures": failures}


def lambda_handler(event, context):
    import boto3
    return handle(event, boto3.client("s3"), os.environ["DATA_BUCKET"], int(os.environ.get("MAX_BYTES", "8388608")))
