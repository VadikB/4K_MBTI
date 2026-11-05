"""Launch the existing app with an explicit component-only upstream fixture."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.test_stand import owned, environment, check_port
from tests.browser_component_app import FIXTURE, validate_activation

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads(args.state.read_bytes())
    env = environment(state)
    env["AGENT4K_COMPONENT_PLAN_FIXTURE"] = FIXTURE
    validate_activation(state, env)
    with owned(state):
        pass
    check_port(state["port"])
    os.execve(sys.executable, [sys.executable, "-m", "uvicorn", "tests.browser_component_app:create_app",
        "--factory", "--host", "127.0.0.1", "--port", str(state["port"]), "--no-access-log"], env)
