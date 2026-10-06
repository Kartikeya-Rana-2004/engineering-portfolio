"""Check real boto3 request shapes via Stubber; makes zero network requests."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import boto3
from botocore.stub import Stubber
from awsflow.demo import MemoryS3, example_event
from awsflow.worker import process_event


def main():
    raw = (ROOT / "examples/requests.jsonl").read_bytes()
    event = example_event()
    # Explicit dummy credentials ensure no credential discovery/metadata requests.
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="testing", aws_secret_access_key="testing")
    captured = []
    fake = MemoryS3(raw)
    put = fake.put_object
    def capture(**kwargs):
        captured.append(kwargs)
        return put(**kwargs)
    fake.put_object = capture
    with contextlib.redirect_stdout(io.StringIO()):
        process_event(event, fake, "offline-demo")
    with Stubber(client) as stubber:
        stubber.add_response("get_object", {"ContentLength": len(raw), "Body": io.BytesIO(raw)}, {"Bucket": "offline-demo", "Key": "bronze/demo.jsonl", "VersionId": "version-1"})
        for call in captured:
            stubber.add_response("put_object", {"ETag": '"stubbed"'}, call)
        with contextlib.redirect_stdout(io.StringIO()):
            result = process_event(event, client, "offline-demo")
        stubber.assert_no_pending_responses()
    evidence = {"verification": "boto3/botocore Stubber request/response validation; no AWS calls", "get_object_requests": 1, "put_object_requests": len(captured), "versioned_read": True, "explicit_sse_s3_writes": all(c["ServerSideEncryption"] == "AES256" for c in captured), "accepted_records": result["accepted"], "boto3_version": boto3.__version__, "live_deployment_verified": False}
    (ROOT / "evidence/awsflow-sdk-verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
