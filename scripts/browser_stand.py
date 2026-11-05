"""Pre-scenario synthetic preparation only; never fabricates assessment outputs."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.test_stand import owned,environment


def prepare_time_variant(connection, *, variant, user_id, profile_id):
    if variant not in {"budget", "deadline"}:
        raise ValueError("BROWSER_TIME_VARIANT_INVALID")
    from Api.m7_cycle_planner import create_plan
    from Api.m10_product_flow import prepare
    # Freeze short QA timing BEFORE selecting/preparing AS. A new revision after
    # preparation correctly invalidates its old route-decision lineage.
    plan = create_plan(connection, personalized_profile_id=profile_id,
        selected_skills=["K1", "K2", "K3", "K4"], created_by=user_id,
        key="browser-time-input", usage_scope="qa",
        time_budget_seconds=30 if variant == "budget" else 3600,
        calendar_window_seconds=30 if variant == "deadline" else 259200)
    prepared = prepare(connection, user_id=user_id, profile_id=profile_id,
        selected_skills=["K1", "K2", "K3", "K4"], key="browser-prepared")
    if (prepared["plan"]["cycle_id"] != plan["cycle_id"]
            or prepared["plan"]["revision_id"] != plan["revision_id"]):
        raise ValueError("BROWSER_TIME_PREPARATION_PLAN_MISMATCH")
    return prepared


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--variant", choices=["ordinary", "budget", "deadline"], default="ordinary")
    parser.add_argument("--internal", action="store_true")
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    with owned(state):
        pass
    if not args.internal:
        state["browser_scenario"] = "acceptance-v1"
        args.state.write_text(json.dumps(state))
        subprocess.run([sys.executable, __file__, "--state", str(args.state), "--variant", args.variant,
                        "--internal"], env=environment(state), check=True)
    elif args.variant != "ordinary":
        from Api.database import get_connection
        with get_connection() as connection:
            user_id = connection.execute("SELECT id FROM users WHERE email='participant@example.test'").fetchone()["id"]
            profile_id = connection.execute("SELECT id FROM assessment_personalized_profiles WHERE user_id=%s AND status='ready'",
                                            (user_id,)).fetchone()["id"]
            prepare_time_variant(connection, variant=args.variant, user_id=user_id, profile_id=profile_id)
            connection.commit()
    print("browser inputs prepared", args.variant)


if __name__ == "__main__":
    main()
