"""Validate records without silently coercing upstream schema changes."""
from collections import Counter
from datetime import datetime
import math


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_contract(contract):
    if not isinstance(contract, dict) or not isinstance(contract.get("fields"), dict):
        raise ValueError("contract requires a fields object")
    if contract.get("unknown_fields", "allow") not in ("allow", "reject"):
        raise ValueError("unknown_fields must be allow or reject")
    for name, rule in contract["fields"].items():
        if rule.get("type") not in ("string", "number", "integer", "timestamp"):
            raise ValueError(f"unsupported type for {name}")
    for comparison in contract.get("comparisons", []):
        if comparison.get("op") != "gte":
            raise ValueError("only gte comparisons supported")
        if any(comparison.get(k) not in contract["fields"] for k in ("left", "right")):
            raise ValueError("comparison references an unknown field")
    return contract


def validate(row, contract):
    errors = []
    if not isinstance(row, dict):
        return ["record:not_object"]
    for name, rule in contract["fields"].items():
        value = row.get(name)
        if value is None or value == "":
            if rule.get("required"):
                errors.append(f"{name}:required")
            continue
        kind = rule["type"]
        good = True
        if kind == "string":
            good = isinstance(value, str)
        elif kind == "integer":
            good = isinstance(value, int) and not isinstance(value, bool)
        elif kind == "number":
            good = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        elif kind == "timestamp":
            try:
                timestamp(value)
            except (ValueError, TypeError):
                good = False
        if not good:
            errors.append(f"{name}:type_{kind}")
            continue
        if "enum" in rule and value not in rule["enum"]:
            errors.append(f"{name}:enum")
        if "min" in rule and value < rule["min"]:
            errors.append(f"{name}:min")
        if "max" in rule and value > rule["max"]:
            errors.append(f"{name}:max")
    if contract.get("unknown_fields") == "reject":
        errors.extend(f"{key}:unknown" for key in sorted(set(row) - set(contract["fields"])))
    for rule in contract.get("comparisons", []):
        left, right = row.get(rule["left"]), row.get(rule["right"])
        if left in (None, "") or right in (None, ""):
            continue
        try:
            if timestamp(left) < timestamp(right):
                errors.append(f"{rule['left']}:before_{rule['right']}")
        except (ValueError, TypeError):
            errors.append("comparison:invalid_timestamp")
    return errors


def profile(rows):
    """Observed types and missingness; a sample is not an authoritative schema."""
    rows = list(rows)
    fields = sorted({key for row in rows if isinstance(row, dict) for key in row})
    result = {}
    for field in fields:
        values = [row.get(field) if isinstance(row, dict) else None for row in rows]
        result[field] = {
            "types": sorted({type(v).__name__ for v in values if v is not None}),
            "null_fraction": sum(v is None for v in values) / len(rows),
        }
    return {"rows": len(rows), "fields": result}


def drift(baseline, current, null_tolerance=0.1):
    old, new = baseline["fields"], current["fields"]
    changes = []
    for name in sorted(set(old) - set(new)):
        changes.append({"field": name, "change": "removed", "severity": "error"})
    for name in sorted(set(new) - set(old)):
        changes.append({"field": name, "change": "added", "severity": "warning"})
    for name in sorted(set(old) & set(new)):
        if old[name]["types"] != new[name]["types"]:
            changes.append({"field": name, "change": "types_changed", "severity": "error"})
        delta = new[name]["null_fraction"] - old[name]["null_fraction"]
        if delta > null_tolerance:
            changes.append({"field": name, "change": "null_fraction_increased", "delta": delta, "severity": "error"})
    return changes


def check(rows, contract):
    validate_contract(contract)
    accepted, rejected = [], []
    reasons = Counter()
    for index, row in enumerate(rows):
        errors = validate(row, contract)
        if errors:
            rejected.append({"index": index, "errors": errors, "record": row})
            reasons.update(errors)
        else:
            accepted.append(row)
    return accepted, rejected, dict(sorted(reasons.items()))
