import copy
import json
from pathlib import Path
import unittest
from contractwatch.core import check, drift, profile, validate, validate_contract

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "contracts/nyc311.json").read_text())
ROW = json.loads((ROOT / "examples/requests.jsonl").read_text().splitlines()[0])


class ContractTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate(ROW, CONTRACT), [])

    def test_required(self):
        row = dict(ROW)
        del row["agency"]
        self.assertIn("agency:required", validate(row, CONTRACT))

    def test_changed_type(self):
        row = dict(ROW, unique_key=123)
        self.assertIn("unique_key:type_string", validate(row, CONTRACT))

    def test_negative_duration(self):
        row = dict(ROW, closed_date="2024-12-01T00:00:00")
        self.assertIn("closed_date:before_created_date", validate(row, CONTRACT))

    def test_unknown_field(self):
        self.assertIn("secret:unknown", validate(dict(ROW, secret="value"), CONTRACT))

    def test_non_object(self):
        self.assertEqual(validate(None, CONTRACT), ["record:not_object"])

    def test_invalid_contract(self):
        contract = copy.deepcopy(CONTRACT)
        contract["fields"]["agency"]["type"] = "strng"
        with self.assertRaises(ValueError):
            validate_contract(contract)

    def test_quarantine_partition(self):
        accepted, rejected, reasons = check([ROW, dict(ROW, unique_key=5)], CONTRACT)
        self.assertEqual((len(accepted), len(rejected)), (1, 1))
        self.assertEqual(reasons["unique_key:type_string"], 1)

    def test_drift(self):
        before = profile([{"id": "a", "value": 3}, {"id": "b", "value": 4}])
        after = profile([{"id": 1, "value": None, "new": "x"}, {"id": 2, "value": 4}])
        changes = drift(before, after)
        self.assertTrue(any(c["change"] == "types_changed" for c in changes))
        self.assertTrue(any(c["change"] == "null_fraction_increased" for c in changes))
        self.assertTrue(any(c["change"] == "added" for c in changes))

    def test_empty_profile(self):
        self.assertEqual(profile([]), {"rows": 0, "fields": {}})

    def test_numeric_contract_rejects_boolean(self):
        contract = {"fields": {"x": {"type": "number", "required": True}}}
        self.assertEqual(validate({"x": True}, contract), ["x:type_number"])


if __name__ == "__main__":
    unittest.main()
