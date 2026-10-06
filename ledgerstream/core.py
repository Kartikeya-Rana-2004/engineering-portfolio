import hashlib
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import uuid


@contextmanager
def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=WAL")
    try:
        with c:
            yield c
    finally:
        c.close()


def validate_order(value):
    if not isinstance(value, dict) or set(value) != {"order_id", "amount_cents", "status"}:
        raise ValueError("order schema mismatch")
    if not isinstance(value["order_id"], str) or not value["order_id"]:
        raise ValueError("order_id required")
    if type(value["amount_cents"]) is not int or value["amount_cents"] < 0:
        raise ValueError("nonnegative integer amount_cents required")
    if value["status"] not in ("placed", "paid", "cancelled"):
        raise ValueError("invalid order status")


class OutboxSource:
    def __init__(self, path, stream="orders-v1"):
        self.path, self.stream = path, stream
        with connect(path) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS orders (order_id TEXT PRIMARY KEY, version INTEGER NOT NULL, deleted INTEGER NOT NULL, payload TEXT);
            CREATE TABLE IF NOT EXISTS outbox (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, envelope TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS source_config (id INTEGER PRIMARY KEY CHECK(id=1), stream TEXT NOT NULL);
            """)
            existing = c.execute("SELECT stream FROM source_config WHERE id=1").fetchone()
            if existing and existing[0] != stream:
                raise ValueError("database belongs to another source stream")
            c.execute("INSERT OR IGNORE INTO source_config VALUES (1,?)", (stream,))

    def change(self, order_id, payload=None, delete=False, fail_after_source=False):
        if not isinstance(order_id, str) or not order_id:
            raise ValueError("order ID required")
        if not delete:
            validate_order(payload)
            if payload["order_id"] != order_id:
                raise ValueError("key mismatch")
        with connect(self.path) as c:
            c.execute("BEGIN IMMEDIATE")
            prior = c.execute("SELECT version FROM orders WHERE order_id=?", (order_id,)).fetchone()
            version = (prior[0] if prior else 0) + 1
            c.execute("INSERT INTO orders VALUES (?,?,?,?) ON CONFLICT(order_id) DO UPDATE SET version=excluded.version,deleted=excluded.deleted,payload=excluded.payload", (order_id, version, int(delete), json.dumps(payload) if not delete else None))
            if fail_after_source:
                raise RuntimeError("injected failure before outbox write")
            event_id = uuid.uuid4().hex
            cursor = c.execute("INSERT INTO outbox(event_id,envelope) VALUES (?,?)", (event_id, "pending"))
            event = {"stream": self.stream, "sequence": cursor.lastrowid, "event_id": event_id,
                     "key": order_id, "version": version, "op": "delete" if delete else "upsert", "after": None if delete else payload}
            c.execute("UPDATE outbox SET envelope=? WHERE sequence=?", (json.dumps(event, sort_keys=True), cursor.lastrowid))
        return event

    def read(self, after=0, limit=1000):
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 10000:
            raise ValueError("invalid polling bounds")
        with connect(self.path) as c:
            return [json.loads(row[0]) for row in c.execute("SELECT envelope FROM outbox WHERE sequence>? ORDER BY sequence LIMIT ?", (after, limit))]


class Projection:
    def __init__(self, path):
        self.path = path
        with connect(path) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS state (stream TEXT,entity_key TEXT,version INTEGER NOT NULL,deleted INTEGER NOT NULL,payload TEXT,PRIMARY KEY(stream,entity_key));
            CREATE TABLE IF NOT EXISTS checkpoints (stream TEXT PRIMARY KEY,sequence INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS receipts (stream TEXT,sequence INTEGER,event_id TEXT UNIQUE NOT NULL,sha256 TEXT NOT NULL,outcome TEXT NOT NULL,PRIMARY KEY(stream,sequence));
            CREATE TABLE IF NOT EXISTS dead_letters (event_id TEXT PRIMARY KEY,reason TEXT NOT NULL,envelope TEXT NOT NULL);
            CREATE VIEW IF NOT EXISTS order_metrics AS SELECT
              json_extract(payload,'$.status') AS status,count(*) AS order_count,
              sum(json_extract(payload,'$.amount_cents')) AS total_amount_cents
              FROM state WHERE deleted=0 GROUP BY 1;
            """)

    def checkpoint(self, stream):
        with connect(self.path) as c:
            row = c.execute("SELECT sequence FROM checkpoints WHERE stream=?", (stream,)).fetchone()
            return row[0] if row else 0

    def apply(self, events, fail_after=None):
        result = {"applied": 0, "replayed": 0, "stale": 0, "quarantined": 0}
        with connect(self.path) as c:
            c.execute("BEGIN IMMEDIATE")
            for index, event in enumerate(events):
                if not isinstance(event, dict):
                    raise ValueError("invalid event envelope")
                for field in ("stream", "event_id"):
                    if not isinstance(event.get(field), str) or not event[field]:
                        raise ValueError("missing routing metadata")
                if type(event.get("sequence")) is not int or event["sequence"] < 1:
                    raise ValueError("sequence must be a positive integer")
                stream, seq, event_id = event["stream"], event["sequence"], event["event_id"]
                digest = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
                receipt = c.execute("SELECT event_id,sha256 FROM receipts WHERE stream=? AND sequence=?", (stream, seq)).fetchone()
                if receipt:
                    if receipt != (event_id, digest):
                        raise ValueError("conflicting event at existing sequence")
                    result["replayed"] += 1
                    continue
                previous = c.execute("SELECT sequence FROM checkpoints WHERE stream=?", (stream,)).fetchone()
                if seq != (previous[0] if previous else 0) + 1:
                    raise ValueError("gap or out-of-order sequence; checkpoint cannot skip events")
                outcome = "applied"
                try:
                    key, version, op = event.get("key"), event.get("version"), event.get("op")
                    if not isinstance(key, str) or not key or type(version) is not int or version < 1:
                        raise ValueError("invalid entity metadata")
                    if op not in ("upsert", "delete"):
                        raise ValueError("unsupported operation")
                    if op == "upsert":
                        validate_order(event.get("after"))
                        if event["after"]["order_id"] != key:
                            raise ValueError("entity key mismatch")
                    elif event.get("after") is not None:
                        raise ValueError("delete must have null after")
                except ValueError as exc:
                    outcome = "quarantined"
                    c.execute("INSERT INTO dead_letters VALUES (?,?,?)", (event_id, str(exc), json.dumps(event, sort_keys=True)))
                if outcome == "applied":
                    prior = c.execute("SELECT version FROM state WHERE stream=? AND entity_key=?", (stream, key)).fetchone()
                    if prior and version <= prior[0]:
                        outcome = "stale"
                    else:
                        c.execute("INSERT INTO state VALUES (?,?,?,?,?) ON CONFLICT(stream,entity_key) DO UPDATE SET version=excluded.version,deleted=excluded.deleted,payload=excluded.payload", (stream, key, version, int(op == "delete"), json.dumps(event["after"]) if op == "upsert" else None))
                c.execute("INSERT INTO receipts VALUES (?,?,?,?,?)", (stream, seq, event_id, digest, outcome))
                c.execute("INSERT INTO checkpoints VALUES (?,?) ON CONFLICT(stream) DO UPDATE SET sequence=excluded.sequence", (stream, seq))
                result[outcome] += 1
                if fail_after is not None and index + 1 == fail_after:
                    raise RuntimeError("injected projection crash")
        return result
