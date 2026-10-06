"""Explicit uploader: no network or AWS actions until invoked by the operator."""
import argparse
import hashlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Upload a bounded JSONL input batch to AWSFlow")
    parser.add_argument("input", type=Path)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="us-east-1")
    args = parser.parse_args()
    payload = args.input.read_bytes()
    if len(payload) > 8 * 1024 * 1024:
        parser.error("input exceeds 8 MiB worker cap; split the batch")
    key = f"bronze/{hashlib.sha256(payload).hexdigest()}.jsonl"
    import boto3
    result = boto3.client("s3", region_name=args.region).put_object(Bucket=args.bucket, Key=key, Body=payload, ContentType="application/x-ndjson", ServerSideEncryption="AES256")
    print({"key": key, "version_id": result.get("VersionId")})


if __name__ == "__main__":
    main()
