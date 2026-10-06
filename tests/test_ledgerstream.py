import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from ledgerstream.core import OutboxSource, Projection


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = OutboxSource(Path(self.temp.name) / "source.sqlite")
        self.sink = Projection(Path(self.temp.name) / "sink.sqlite")
        self.order = {"order_id": "o1", "amount_cents": 1200, "status": "placed"}

    def scalar(self, query):
        with sqlite3.connect(self.sink.path) as c:
            return c.execute(query).fetchone()[0]

    def test_outbox_and_source_rollback_together(self):
        with self.assertRaises(RuntimeError):
            self.source.change("o1", self.order, fail_after_source=True)
        self.assertEqual(self.source.read(), [])
        with sqlite3.connect(self.source.path) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM orders").fetchone()[0], 0)

    def test_source_change_creates_event(self):
        event = self.source.change("o1", self.order)
        self.assertEqual(event["version"], 1)
        self.assertEqual(self.source.read(), [event])

    def test_replay_is_noop(self):
        event = self.source.change("o1", self.order)
        self.sink.apply([event])
        self.assertEqual(self.sink.apply([event])["replayed"], 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM receipts"), 1)

    def test_update_changes_aggregate(self):
        self.source.change("o1", self.order)
        self.source.change("o1", dict(self.order, amount_cents=2200))
        self.sink.apply(self.source.read())
        self.assertEqual(self.scalar("SELECT total_amount_cents FROM order_metrics"), 2200)

    def test_delete_retains_version_and_removes_metrics(self):
        self.source.change("o1", self.order)
        self.source.change("o1", delete=True)
        self.sink.apply(self.source.read())
        self.assertEqual(self.scalar("SELECT count(*) FROM order_metrics"), 0)
        self.assertEqual(self.scalar("SELECT version FROM state"), 2)

    def test_stale_upsert_cannot_resurrect_deleted_order(self):
        first = self.source.change("o1", self.order)
        self.source.change("o1", delete=True)
        self.sink.apply(self.source.read())
        stale = dict(first, sequence=3, event_id="late-event")
        self.assertEqual(self.sink.apply([stale])["stale"], 1)
        self.assertEqual(self.scalar("SELECT deleted FROM state"), 1)
        self.assertEqual(self.sink.checkpoint("orders-v1"), 3)

    def test_gap_does_not_advance_checkpoint(self):
        self.source.change("o1", self.order)
        second = self.source.change("o1", dict(self.order, status="paid"))
        with self.assertRaises(ValueError):
            self.sink.apply([second])
        self.assertEqual(self.sink.checkpoint("orders-v1"), 0)

    def test_invalid_payload_quarantined_and_checkpointed(self):
        event = self.source.change("o1", self.order)
        bad = dict(event, after=dict(self.order, amount_cents=-1))
        result = self.sink.apply([bad])
        self.assertEqual(result["quarantined"], 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM dead_letters"), 1)
        self.assertEqual(self.sink.checkpoint("orders-v1"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM state"), 0)

    def test_conflicting_replay_rejected(self):
        event = self.source.change("o1", self.order)
        self.sink.apply([event])
        with self.assertRaises(ValueError):
            self.sink.apply([dict(event, op="delete", after=None)])

    def test_crash_rolls_back_state_receipts_and_checkpoint(self):
        self.source.change("o1", self.order)
        self.source.change("o2", dict(self.order, order_id="o2"))
        with self.assertRaises(RuntimeError):
            self.sink.apply(self.source.read(), fail_after=1)
        self.assertEqual(self.sink.checkpoint("orders-v1"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM state"), 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM receipts"), 0)
        self.assertEqual(self.sink.apply(self.source.read())["applied"], 2)

    def test_invalid_routing_blocks_batch(self):
        with self.assertRaises(ValueError):
            self.sink.apply([{"op": "upsert"}])

    def test_one_source_stream_per_database(self):
        with self.assertRaises(ValueError):
            OutboxSource(self.source.path, stream="different")


if __name__ == "__main__":
    unittest.main()
