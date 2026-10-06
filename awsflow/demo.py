"""Offline demo uses an in-memory S3 adapter, not a real AWS deployment."""
import io
import json
from pathlib import Path
import tempfile
from .worker import process_event


class MemoryS3:
    def __init__(self, raw):
        self.raw = raw
        self.objects = {}
        self.writes = []

    def get_object(self, **kwargs):
        return {"ContentLength": len(self.raw), "Body": io.BytesIO(self.raw)}

    def put_object(self, **kwargs):
        self.objects[kwargs["Key"]] = kwargs["Body"]
        self.writes.append(kwargs["Key"])
        return {"ETag": "offline"}


def example_event():
    return {"source": "aws.s3", "detail-type": "Object Created", "time": "2026-10-06T12:00:00Z",
            "detail": {"bucket": {"name": "offline-demo"}, "object": {"key": "bronze/demo.jsonl", "version-id": "version-1"}}}


def main():
    root = Path(__file__).resolve().parents[1]
    client = MemoryS3((root / "examples/requests.jsonl").read_bytes())
    event = example_event()
    first = process_event(event, client, "offline-demo")
    snapshot = dict(client.objects)
    process_event(event, client, "offline-demo")
    assert client.objects == snapshot
    assert len([key for key in client.objects if key.startswith("commits/")]) == 1
    output = root / "data/awsflow-offline"
    output.mkdir(parents=True, exist_ok=True)
    for key, payload in client.objects.items():
        path = output / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    evidence = {"execution": "offline in-memory S3 adapter; no AWS services invoked",
                "input_rows": first["source_rows"], "accepted": first["accepted"],
                "partition_count": len(first["partitions"]), "unique_objects": len(client.objects),
                "duplicate_event_preserved_object_bytes": client.objects == snapshot,
                "commit_written_last": client.writes[-1].startswith("commits/"),
                "cloud_deployment_verified": False}
    (root / "evidence/awsflow-offline-verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
