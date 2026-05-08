"""
Sensor-aware safety gate test utility — Phase 4D.

Tests safety gate logic directly without running the full shell.
Does not call body execution. Does not require config changes.

Tests check_sensor_gates() directly for sensor gate behavior,
then validates that normal shell mode still blocks step_forward
regardless of sensor state.

Usage:
    python tools/test_sensor_safety.py
"""

import sys
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain.state import RobotState
from body.safety import check_safety, check_sensor_gates, is_movement_action, _load_config


def make_mobile_state(distance_status=None, distance_cm=None):
    """Create a mobile-mode state with optional sensor values."""
    state = RobotState()
    state.mode             = "mobile"
    state.movement_enabled = True
    if distance_status is not None:
        state.sensors["distance_status"] = distance_status
    if distance_cm is not None:
        state.sensors["distance_cm"] = distance_cm
    return state


def run_tests():
    config = _load_config()
    action = "step_forward"
    passed = 0
    failed = 0

    print("\n[SENSOR SAFETY TEST]")
    print(f"  Testing action : '{action}'")
    print(f"  Using          : check_sensor_gates() directly\n")

    cases = [
        ("safe",     "safe",     30.1,  True,  "approved by sensor gate"),
        ("warning",  "warning",  20.0,  True,  "approved by sensor gate"),
        ("critical", "critical", 10.0,  False, "blocked by sensor gate"),
        ("missing",  None,       None,  True,  "approved — unknown_blocks_movement=false"),
    ]

    for label, dist_status, dist_cm, expect_approved, note in cases:
        state = make_mobile_state(dist_status, dist_cm)
        approved, reason = check_sensor_gates(action, state, config)
        ok = (approved == expect_approved)
        symbol = "✓" if ok else "✗"
        result = "approved" if approved else "blocked"
        print(f"  {symbol} {label:<10} → {result:<10}  ({note})")
        if not ok:
            print(f"    EXPECTED approved={expect_approved}, got approved={approved}")
            print(f"    reason: {reason}")
            failed += 1
        else:
            passed += 1

    # Full check_safety: mobile mode, no sensor → approved
    print()
    state_clear = make_mobile_state()
    approved, reason = check_safety(action, state_clear)
    ok = approved
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} full gate (mobile, no sensor)  → {'approved' if approved else 'blocked'}")
    if ok:
        passed += 1
    else:
        print(f"    UNEXPECTED block: {reason}")
        failed += 1

    # Full check_safety: mobile mode, critical sensor → blocked
    state_crit = make_mobile_state("critical", 10.0)
    approved, reason = check_safety(action, state_crit)
    ok = not approved
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} full gate (mobile, critical)    → {'blocked' if not approved else 'approved'}")
    if ok:
        passed += 1
    else:
        print(f"    UNEXPECTED approval")
        failed += 1

    # Shell mode: step_forward always blocked regardless of sensor state
    print()
    print("  --- Shell mode verification ---")
    state_shell_safe = RobotState()
    state_shell_safe.sensors["distance_status"] = "safe"
    approved_shell, reason_shell = check_safety(action, state_shell_safe)
    ok_shell = not approved_shell
    symbol = "✓" if ok_shell else "✗"
    print(f"  {symbol} shell mode + sensor=safe → step_forward blocked (mode gate)")
    if ok_shell:
        passed += 1
    else:
        print(f"    UNEXPECTED approval in shell mode")
        failed += 1

    print()
    total = passed + failed
    if failed == 0:
        print(f"  Result: PASS ({passed}/{total})")
    else:
        print(f"  Result: FAIL ({failed}/{total} failed)")
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
