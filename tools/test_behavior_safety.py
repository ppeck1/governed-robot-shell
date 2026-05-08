"""
Behavior safety test utility — Phase 6A.

Ensures behavior-proposed actions pass through safety correctly.
Does not execute body actions.

Usage:
    python tools/test_behavior_safety.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain.state import RobotState
from body.safety import check_safety


def run():
    print("\n[BEHAVIOR SAFETY TEST]\n")
    state = RobotState()
    passed = failed = 0

    cases = [
        ("idle_flutter",         True,  "safe expressive action in shell mode"),
        ("head_turn_left_right", True,  "safe expressive action in shell mode"),
        ("play_chirp",           True,  "safe expressive action in shell mode"),
        ("express_curious",      True,  "safe expressive action in shell mode"),
        ("step_forward",         False, "locomotion blocked in shell mode"),
    ]

    for action, expect_approved, note in cases:
        approved, reason = check_safety(action, state)
        ok = (approved == expect_approved)
        symbol = "✓" if ok else "✗"
        result = "approved" if approved else "blocked"
        print(f"  {symbol} {action:<26} → {result:<10}  ({note})")
        if not ok:
            print(f"      expected approved={expect_approved}, got {approved}")
            print(f"      reason: {reason}")
            failed += 1
        else:
            passed += 1

    total = passed + failed
    print(f"\n  Result: {'PASS' if failed == 0 else 'FAIL'} ({passed}/{total})\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
