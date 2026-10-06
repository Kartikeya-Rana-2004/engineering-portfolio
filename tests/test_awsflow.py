import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import unittest
from awsflow.demo import MemoryS3, example_event
from awsflow.worker import encode_jsonl, handle, process_event, transform
from infra.build_awsflow import template

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT / "examples/requests.jsonl").read_bytes()
ROW = json.loads(RAW.splitlines()[0])


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.event = example_event()
        self.client = MemoryS3(RAW)
        self.silence = contextlib.redirect_stdout(io.StringIO())
        self.silence.__enter__()
        self.addCleanup(self.silence.__exit__, None, None, None)

    def test_partition_transform(self):
        parts, rejects, summary = transform(RAW, "batch", self.event["time"])
        self.assertEqual(sorted(parts), ["2025-01-01", "2025-01-02"])
        self.assertEqual(parts["2025-01-01"][0]["resolution_hours"], 4)
        self.assertEqual(summary["accepted"], 3)
        self.assertEqual(rejects, [])

    def test_duplicate_event_is_byte_stable(self):
        process_event(self.event, self.client, "offline-demo")
        first = dict(self.client.objects)
        process_event(self.event, self.client, "offline-demo")
        self.assertEqual(first, self.client.objects)
        self.assertEqual(sum(k.startswith("commits/") for k in first), 1)

    def test_commit_last(self):
        summary = process_event(self.event, self.client, "offline-demo")
        self.assertEqual(self.client.writes[-1], f"commits/{summary['batch_id']}.json")

    def test_gzip_payload_round_trip(self):
        process_event(self.event, self.client, "offline-demo")
        payloads = [gzip.decompress(v) for k, v in self.client.objects.items() if k.startswith("silver/")]
        self.assertEqual(sum(len(p.splitlines()) for p in payloads), 3)

    def test_blocked_batch_never_commits(self):
        client = MemoryS3(encode_jsonl([dict(ROW, closed_date="2020-01-01")]))
        result = process_event(self.event, client, "offline-demo")
        self.assertEqual(result["status"], "blocked_quality_gate")
        self.assertTrue(any(k.startswith("quarantine/") for k in client.objects))
        self.assertFalse(any(k.startswith(("silver/", "commits/")) for k in client.objects))

    def test_malformed_json_quarantined(self):
        parts, rejected, summary = transform(b"not-json\n", "batch", self.event["time"])
        self.assertEqual(summary["status"], "blocked_quality_gate")
        self.assertEqual(rejected[0]["errors"], ["record:invalid_json"])
        self.assertEqual(parts, {})

    def test_reject_within_budget(self):
        parts, rejected, summary = transform(encode_jsonl([ROW] * 20 + [dict(ROW, unique_key=2)]), "batch", self.event["time"])
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(len(rejected), 1)
        self.assertEqual(sum(len(rows) for rows in parts.values()), 20)

    def test_row_cap(self):
        with self.assertRaises(ValueError):
            transform(RAW, "batch", self.event["time"], max_rows=1)

    def test_byte_cap(self):
        with self.assertRaises(ValueError):
            process_event(self.event, self.client, "offline-demo", max_bytes=10)

    def test_reject_other_bucket(self):
        with self.assertRaises(ValueError):
            process_event(self.event, self.client, "different-bucket")

    def test_reject_output_event_prevents_loop(self):
        self.event["detail"]["object"]["key"] = "silver/dt=2025-01-01/file.jsonl"
        with self.assertRaises(ValueError):
            process_event(self.event, self.client, "offline-demo")

    def test_require_version(self):
        del self.event["detail"]["object"]["version-id"]
        with self.assertRaises(ValueError):
            process_event(self.event, self.client, "offline-demo")

    def test_new_source_version_has_distinct_identity(self):
        first = process_event(self.event, self.client, "offline-demo")
        self.event["detail"]["object"]["version-id"] = "version-2"
        second = process_event(self.event, self.client, "offline-demo")
        self.assertNotEqual(first["batch_id"], second["batch_id"])

    def test_failed_partition_write_does_not_commit(self):
        original = self.client.put_object
        def fail(**kwargs):
            if "dt=2025-01-02" in kwargs["Key"]:
                raise OSError("injected failure")
            return original(**kwargs)
        self.client.put_object = fail
        with self.assertRaises(OSError):
            process_event(self.event, self.client, "offline-demo")
        self.assertTrue(any(k.startswith("silver/") for k in self.client.objects))
        self.assertFalse(any(k.startswith("commits/") for k in self.client.objects))
        self.client.put_object = original
        process_event(self.event, self.client, "offline-demo")
        self.assertEqual(sum(k.startswith("commits/") for k in self.client.objects), 1)

    def test_partial_batch_failure_only_retries_bad_item(self):
        messages = {"Records": [{"messageId": "good", "body": json.dumps(self.event)}, {"messageId": "bad", "body": "not-json"}]}
        result = handle(messages, self.client, "offline-demo")
        self.assertEqual(result, {"batchItemFailures": [{"itemIdentifier": "bad"}]})

    def test_quality_block_is_acknowledged(self):
        client = MemoryS3(b"not-json\n")
        event = {"Records": [{"messageId": "bad-data", "body": json.dumps(self.event)}]}
        self.assertEqual(handle(event, client, "offline-demo"), {"batchItemFailures": []})


class InfrastructureTests(unittest.TestCase):
    def test_infra_contracts_match_worker(self):
        resources = template()["Resources"]
        self.assertEqual(resources["Worker"]["Properties"]["Handler"], "awsflow.worker.lambda_handler")
        self.assertIn("ReportBatchItemFailures", resources["QueueMapping"]["Properties"]["FunctionResponseTypes"])
        self.assertEqual(resources["BronzeRule"]["Properties"]["EventPattern"]["detail"]["object"]["key"], [{"prefix": "bronze/"}])
        self.assertEqual(resources["DataBucket"]["Properties"]["VersioningConfiguration"]["Status"], "Enabled")

    def test_partition_projection_matches_keys(self):
        parameters = template()["Resources"]["SilverTable"]["Properties"]["TableInput"]["Parameters"]
        self.assertEqual(parameters["storage.location.template"], {"Fn::Sub": "s3://${DataBucket}/silver/dt=${!dt}/"})


if __name__ == "__main__":
    unittest.main()
