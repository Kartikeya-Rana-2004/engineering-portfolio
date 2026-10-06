"""Deterministic change/replay/recovery exercise on isolated local databases."""
import json
from pathlib import Path
import sqlite3
import tempfile
from .core import OutboxSource, Projection


def main():
    with tempfile.TemporaryDirectory() as directory:
        source = OutboxSource(Path(directory) / "source.sqlite")
        sink = Projection(Path(directory) / "projection.sqlite")
        source.change("o-1", {"order_id": "o-1", "amount_cents": 5000, "status": "placed"})
        source.change("o-2", {"order_id": "o-2", "amount_cents": 2500, "status": "paid"})
        source.change("o-1", {"order_id": "o-1", "amount_cents": 5000, "status": "paid"})
        source.change("o-2", delete=True)
        events = source.read()
        try:
            sink.apply(events, fail_after=2)
        except RuntimeError:
            pass
        checkpoint_after_crash = sink.checkpoint("orders-v1")
        recovery = sink.apply(events)
        replay = sink.apply(events)
        with sqlite3.connect(sink.path) as c:
            metrics = c.execute("SELECT * FROM order_metrics").fetchall()
            tombstones = c.execute("SELECT count(*) FROM state WHERE deleted=1").fetchone()[0]
        assert checkpoint_after_crash == 0 and recovery["applied"] == 4 and replay["replayed"] == 4
        assert metrics == [("paid", 1, 5000)] and tombstones == 1
    evidence = {"execution": "real local SQLite source/outbox and projection; synthetic orders; no Kafka or PostgreSQL deployment",
                "events": len(events), "checkpoint_after_injected_crash": checkpoint_after_crash,
                "recovery": recovery, "replay": replay, "final_metrics": metrics, "retained_delete_tombstones": tombstones}
    root = Path(__file__).resolve().parents[1]
    (root / "evidence/ledgerstream-verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
