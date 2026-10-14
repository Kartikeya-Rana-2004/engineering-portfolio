import unittest
from signalworks.scenarios import build_traces

class SignalWorksTests(unittest.TestCase):
    def setUp(self):
        self.data = build_traces()

    def steps(self, name):
        return next(s['steps'] for s in self.data['scenarios'] if s['id'] == name)

    def test_reproducible(self):
        self.assertEqual(self.data, build_traces())

    def test_schema(self):
        self.assertEqual(self.data['schema_version'], 1)
        self.assertEqual(len(self.data['scenarios']), 8)
        for scenario in self.data['scenarios']:
            for step in scenario['steps']:
                self.assertTrue({'event_id','sequence','version','disposition','state','explanation'} <= step.keys())
                self.assertGreaterEqual(step['state']['paid_cents'], 0)

    def test_duplicates_and_replay_do_not_change_state(self):
        for name in ('duplicate', 'replay'):
            steps = self.steps(name)
            self.assertEqual(steps[-2]['state'], steps[-1]['state'])
            self.assertEqual(steps[-1]['disposition'], 'replayed')

    def test_crash_rolls_back_then_reopens_and_recovers(self):
        steps = self.steps('recovery')
        self.assertEqual(steps[0]['state'], steps[1]['state'])
        self.assertEqual(steps[1]['disposition'], 'rolled_back')
        self.assertEqual(steps[-1]['state']['checkpoint'], 2)
        self.assertEqual(steps[-1]['state']['paid_cents'], 7500)

    def test_quarantine_continues(self):
        steps = self.steps('quarantine')
        self.assertEqual(steps[1]['state']['quarantine_count'], 1)
        self.assertEqual(steps[-1]['state']['checkpoint'], 2)
        self.assertEqual(steps[-1]['state']['paid_cents'], 2500)

    def test_tombstone_cannot_be_resurrected(self):
        steps = self.steps('tombstone')
        self.assertEqual(steps[-1]['disposition'], 'stale')
        self.assertEqual(steps[-1]['state']['active_orders'], 0)
        self.assertEqual(steps[-1]['state']['tombstones'], 1)
        self.assertEqual(steps[-1]['state']['checkpoint'], 3)

    def test_gap_and_conflict_preserve_state(self):
        for name in ('gap','conflict'):
            steps = self.steps(name)
            self.assertEqual(steps[-2]['state'], steps[-1]['state'])
            self.assertEqual(steps[-1]['disposition'], 'blocked')
