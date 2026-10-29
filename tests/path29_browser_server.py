"""Run the PATH29 test harness only against a validated owned localhost database."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import owned, environment, check_port

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    check_port(state['port'])
    env = environment(state)
    env['AGENT4K_PATH29_TEST_APP'] = '1'
    os.chdir(ROOT)
    os.execve(sys.executable, [sys.executable, '-m', 'uvicorn', 'tests.path29_browser_app:app',
        '--host', '127.0.0.1', '--port', str(state['port']), '--no-access-log'], env)
