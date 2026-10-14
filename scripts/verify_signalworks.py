"""Verify transaction contracts and exact reproducibility of both public trace copies."""
from pathlib import Path
import json
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from signalworks.scenarios import build_traces

for pattern in ('test_ledgerstream.py', 'test_signalworks.py'):
    subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', pattern, '-v'], cwd=ROOT, check=True)
expected = json.dumps(build_traces(), indent=2, sort_keys=True) + '\n'
for name in ('evidence/signalworks-traces.json', 'demos/signalworks/traces.json'):
    if (ROOT / name).read_text() != expected:
        raise SystemExit(f'STALE recorded evidence: {name}. Run python3 -m signalworks and node demos/signalworks/build.mjs')
print('Verified 8 reproducible SQLite scenarios; canonical and browser traces match.')
