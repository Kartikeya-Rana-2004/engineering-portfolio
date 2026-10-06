import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from civicflow.pipeline import fetch, load
from civicflow.report import render

ROOT = Path(__file__).resolve().parents[1]
ROWS = [json.loads(line) for line in (ROOT / "examples/requests.jsonl").read_text().splitlines()]


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "warehouse.sqlite"

    def scalar(self, query):
        with sqlite3.connect(self.db) as c:
            return c.execute(query).fetchone()[0]

    def test_replay_does_not_duplicate(self):
        first, _ = load(ROWS, self.db)
        second, _ = load(ROWS, self.db)
        self.assertEqual(first["inserted"], 3)
        self.assertEqual(second["unchanged"], 3)
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(self.scalar("SELECT count(*) FROM requests"), 3)

    def test_correction_updates_in_place(self):
        load(ROWS, self.db)
        changed = dict(ROWS[1], closed_date="2025-01-01T15:00:00", status="Closed")
        result, _ = load([changed], self.db)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(self.scalar("SELECT resolution_hours FROM requests WHERE unique_key='demo-002'"), 4)
        self.assertEqual(self.scalar("SELECT count(*) FROM requests"), 3)

    def test_gate_preserves_existing_data(self):
        load(ROWS, self.db)
        bad = dict(ROWS[0], closed_date="2020-01-01")
        result, rejected = load([bad], self.db)
        self.assertEqual(result["status"], "blocked_quality_gate")
        self.assertEqual(len(rejected), 1)
        self.assertEqual(self.scalar("SELECT resolution_hours FROM requests WHERE unique_key='demo-001'"), 4)
        self.assertEqual(self.scalar("SELECT count(*) FROM runs"), 1)

    def test_quarantine_when_within_budget(self):
        result, _ = load(ROWS + [dict(ROWS[0], unique_key=5)], self.db, 0.3)
        self.assertEqual(result["quarantined"], 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM quarantine"), 1)
        self.assertEqual(self.scalar("SELECT count(*) FROM requests"), 3)

    def test_gold_reconciles(self):
        load(ROWS, self.db)
        self.assertEqual(self.scalar("SELECT sum(request_count) FROM daily_service_metrics"), 3)
        self.assertEqual(self.scalar("SELECT sum(closed_count) FROM daily_service_metrics"), 2)

    def test_transaction_rolls_back(self):
        load(ROWS, self.db)
        with sqlite3.connect(self.db) as c:
            c.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON requests WHEN NEW.unique_key='fail' BEGIN SELECT RAISE(ABORT,'injected'); END;")
        with self.assertRaises(sqlite3.IntegrityError):
            load([dict(ROWS[0], unique_key="new"), dict(ROWS[0], unique_key="fail")], self.db)
        self.assertEqual(self.scalar("SELECT count(*) FROM requests"), 3)

    @patch("civicflow.pipeline.get_json")
    def test_fetch_pages_and_detects_truncation(self, mocked):
        mocked.side_effect = [[ROWS[0]], [ROWS[1]], [{"unique_key": "next"}]]
        rows, truncated = fetch("2025-01-01", "2025-01-08", max_rows=2, page_size=1)
        self.assertEqual(len(rows), 2)
        self.assertTrue(truncated)
        self.assertIn("%24order=created_date+ASC%2Cunique_key+ASC", mocked.call_args_list[0].args[0])

    @patch("civicflow.pipeline.get_json")
    def test_fetch_complete_window(self, mocked):
        mocked.side_effect = [ROWS[:2], []]
        rows, truncated = fetch("2025-01-01", "2025-01-08", max_rows=10, page_size=2)
        self.assertEqual(len(rows), 2)
        self.assertFalse(truncated)

    def test_bad_window(self):
        with self.assertRaises(ValueError):
            fetch("2025-01-08", "2025-01-01")

    def test_dashboard_escapes_text(self):
        load([dict(ROWS[0], complaint_type="<script>alert(1)</script>")], self.db)
        output = Path(self.temp.name) / "dashboard.html"
        render(self.db, output)
        self.assertIn("&lt;script&gt;", output.read_text())
        self.assertNotIn("<script>", output.read_text())

    def test_empty_dashboard(self):
        load([], self.db)
        output = Path(self.temp.name) / "empty.html"
        render(self.db, output)
        self.assertIn("Unavailable", output.read_text())


if __name__ == "__main__":
    unittest.main()
