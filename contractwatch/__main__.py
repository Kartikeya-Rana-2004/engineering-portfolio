import argparse
import json
from pathlib import Path
from .core import check, drift, profile


def main():
    parser = argparse.ArgumentParser(description="Check JSONL record contracts and sampled schema drift")
    parser.add_argument("input", type=Path)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/contract-report.json"))
    parser.add_argument("--null-tolerance", type=float, default=0.1)
    args = parser.parse_args()
    if not 0 <= args.null_tolerance <= 1:
        parser.error("null tolerance must be between 0 and 1")
    rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
    contract = json.loads(args.contract.read_text())
    accepted, rejected, reasons = check(rows, contract)
    snapshot = profile(rows)
    changes = drift(json.loads(args.baseline.read_text()), snapshot, args.null_tolerance) if args.baseline else []
    report = {"accepted": len(accepted), "rejected": len(rejected), "reasons": reasons, "profile": snapshot, "drift": changes}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 1 if rejected or any(c["severity"] == "error" for c in changes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
