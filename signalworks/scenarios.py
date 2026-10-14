"""Run real SQLite transactions, then serialize committed state for the browser."""
from copy import deepcopy
from itertools import count
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
from uuid import UUID
from ledgerstream.core import OutboxSource, Projection

STREAM = 'orders-v1'

def snapshot(projection):
    with sqlite3.connect(projection.path) as db:
        scalar = lambda q: db.execute(q).fetchone()[0]
        return {
            'checkpoint': projection.checkpoint(STREAM),
            'receipt_count': scalar('SELECT count(*) FROM receipts'),
            'quarantine_count': scalar('SELECT count(*) FROM dead_letters'),
            'active_orders': scalar('SELECT count(*) FROM state WHERE deleted=0'),
            'tombstones': scalar('SELECT count(*) FROM state WHERE deleted=1'),
            'paid_cents': scalar("SELECT coalesce(sum(total_amount_cents),0) FROM order_metrics WHERE status='paid'"),
            'entities': [dict(key=r[0], version=r[1], deleted=bool(r[2])) for r in db.execute('SELECT entity_key,version,deleted FROM state ORDER BY entity_key')],
        }

TITLES = {
    'success': ('The happy path', 'Two orders become durable, queryable state.'),
    'duplicate': ('Deliver it twice', 'Delivery can repeat. Revenue must not.'),
    'quarantine': ('Catch a poison record', 'Isolate bad data and let the next valid event through.'),
    'recovery': ('Crash. Roll back. Recover.', 'A checkpoint is only useful when it commits with the data.'),
    'replay': ('Replay the entire batch', 'Reprocessing history leaves the current totals unchanged.'),
    'tombstone': ('Keep a deletion deleted', 'An older entity version must not resurrect an order.'),
    'gap': ('Refuse a sequence gap', 'Never advance a checkpoint past an unseen event.'),
    'conflict': ('Reject conflicting history', 'The same sequence cannot quietly change its meaning.'),
}

def run_scenario(name, root):
    source = OutboxSource(root / 'source.sqlite')
    sink = Projection(root / 'sink.sqlite')
    steps = []
    def record(disposition, explanation, event=None, fixture=False):
        event = event or {}
        steps.append(dict(event_id=event.get('event_id'), sequence=event.get('sequence'),
                          version=event.get('version'), disposition=disposition,
                          transport_fixture=fixture, state=snapshot(sink), explanation=explanation))
    def apply(event, explanation, fixture=False):
        result = sink.apply([event])
        disposition = next(key for key, value in result.items() if value)
        record(disposition, explanation, event, fixture)
    record('ready', 'Source events are durable in the outbox; the projection has not consumed them yet.')
    first = source.change('order-001', dict(order_id='order-001', amount_cents=5000, status='paid'))
    second = source.change('order-002', dict(order_id='order-002', amount_cents=2500, status='paid')) if name != 'tombstone' else None
    if name == 'recovery':
        try:
            sink.apply(source.read(), fail_after=1)
        except RuntimeError as exc:
            record('rolled_back', f'{exc}. The first write, its receipt and checkpoint all rolled back.', first)
        sink = Projection(sink.path)
        for event in source.read(after=sink.checkpoint(STREAM)):
            apply(event, 'Reopened the SQLite projection and resumed from its committed checkpoint.')
    elif name == 'quarantine':
        bad = deepcopy(first)
        bad['after']['amount_cents'] = -1
        apply(bad, 'Transport fixture: a negative amount is quarantined, with its receipt and checkpoint committed.', True)
        apply(second, 'The next valid order commits; the poison record does not block progress.')
    elif name == 'gap':
        try:
            sink.apply([second])
        except ValueError as exc:
            record('blocked', str(exc), second)
    else:
        apply(first, 'The order, receipt and checkpoint commit in one sink transaction.')
        if name == 'duplicate':
            apply(first, 'Exact envelope already has a receipt: no second write and no extra revenue.')
        elif name == 'conflict':
            changed = deepcopy(first)
            changed['after']['amount_cents'] = 9999
            try:
                sink.apply([changed])
            except ValueError as exc:
                record('blocked', str(exc), changed, True)
        elif name == 'tombstone':
            # The sequence comes from the source; the stale version is an explicit transport fixture.
            deletion = source.change('order-001', delete=True)
            apply(deletion, 'Deletion retains entity version 2 as a tombstone.')
            stale = dict(first, sequence=3, event_id='stale-transport-fixture')
            apply(stale, 'Transport fixture: a new stream sequence carries old entity version 1; tombstone version 2 wins.', True)
        else:
            apply(second, 'The next source sequence commits. Current paid-order total is $75.00 in synthetic data.')
            if name == 'replay':
                result = sink.apply(source.read())
                record('replayed', f"Replayed {result['replayed']} exact envelopes. All committed state is unchanged.", second)
    title, description = TITLES[name]
    return dict(id=name, title=title, description=description, steps=steps)

def build_traces():
    scenarios = []
    for name in TITLES:
        identifiers = count(1)
        # Scoped reproducibility only: production LedgerStream still uses random UUIDs.
        with tempfile.TemporaryDirectory() as tmp, patch('ledgerstream.core.uuid.uuid4', side_effect=lambda: UUID(int=next(identifiers))):
            scenarios.append(run_scenario(name, Path(tmp)))
    return dict(schema_version=1, engine='LedgerStream / real local SQLite transactions',
                disclosure='Interactive replay of a recorded local run using synthetic data.', scenarios=scenarios)
