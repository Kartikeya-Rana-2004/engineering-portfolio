"""Run selected unittest and Node test files without requiring a second framework."""
from pathlib import Path
import subprocess
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
suite = unittest.TestSuite()
node = []
for name in sys.argv[1:]:
    path = Path(name)
    if path.suffix == '.py' and path.name.startswith('test_') and path.parent == Path('tests'):
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=path.name))
    elif path.suffix == '.mjs' and path.name.endswith('.test.mjs') and path.parent == Path('demos/signalworks'):
        node.append(name)
    else:
        raise SystemExit(f'Unsupported selected test: {name}')
count = suite.countTestCases()
if not count and not node:
    raise SystemExit('No tests selected')
if count and not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
    raise SystemExit(1)
if node:
    subprocess.run(['node', '--test', *node], cwd=ROOT, check=True)
else:
    # The generic gate recognizes TAP count summaries; unittest still prints its own report.
    print(f'# tests {count}\n# fail 0')
