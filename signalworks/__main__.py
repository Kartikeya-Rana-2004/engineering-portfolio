import argparse
import json
from pathlib import Path
from .scenarios import build_traces

parser = argparse.ArgumentParser(description='Record reproducible SignalWorks SQLite experiments.')
parser.add_argument('--output', type=Path, default=Path('evidence/signalworks-traces.json'))
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(build_traces(), indent=2, sort_keys=True) + '\n')
print(f'Recorded 8 scenarios: {args.output}')
