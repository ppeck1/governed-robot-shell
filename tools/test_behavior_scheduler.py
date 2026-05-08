"""
Behavior scheduler test utility — Phase 6A.

Tests scheduler logic without running the full shell.
Does not call body, planner, safety, or LLM.

Usage:
    python tools/test_behavior_scheduler.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from behavior.behavior_scheduler import BehaviorScheduler

_SAFE_CONFIG = {
    "enabled": True,
    "mode": "passive",
    "idle_after_seconds": 20.0,
    "min_action_cooldown_seconds": 15.0,
    "max_actions_per_session": 3,
    "allowed_actions": ["idle_flutter", "play_chirp",
                        "head_turn_left_right", "express_curious"],
    "weights": {"idle_flutter": 1.0, "play_chirp": 1.0,
                "head_turn_left_right": 1.0, "express_curious": 1.0},
    "blocked_actions": ["step_forward"],
}

LOCOMOTION_ATTEMPTS = [
    "step_forward", "walk_forward", "move_forward", "crawl_left"
]


def run():
    passed = failed = 0
    print("\n[BEHAVIOR SCHEDULER TEST]\n")

    # 1. Disabled scheduler returns no action
    sched = BehaviorScheduler(config={"enabled": False})
    d = sched.tick(force=True)
    ok = not d["should_run"] and d["action"] is None
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} disabled              → should_run={d['should_run']} reason='{d['reason']}'")
    passed += ok; failed += (not ok)

    # 2. Normal tick before idle threshold — not forced
    sched2 = BehaviorScheduler(config=_SAFE_CONFIG)
    sched2.notify_user_activity()         # reset to now
    d = sched2.tick(force=False)
    ok = not d["should_run"]
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} idle threshold        → should_run={d['should_run']} reason='{d['reason'][:40]}'")
    passed += ok; failed += (not ok)

    # 3. Forced tick proposes an allowed action
    d = sched2.tick(force=True)
    ok = d["should_run"] and d["action"] in _SAFE_CONFIG["allowed_actions"]
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} forced allowed action → action='{d['action']}' in allowed list")
    passed += ok; failed += (not ok)

    # 4. Proposed action is never locomotion
    all_non_loco = True
    loco_seen    = []
    for _ in range(50):
        sched_fresh = BehaviorScheduler(config=_SAFE_CONFIG)
        d = sched_fresh.tick(force=True)
        if d["action"] in LOCOMOTION_ATTEMPTS:
            all_non_loco = False
            loco_seen.append(d["action"])
    ok = all_non_loco
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} no locomotion         → step_forward never proposed (50 samples)"
          + (f" PROBLEM: {loco_seen}" if loco_seen else ""))
    passed += ok; failed += (not ok)

    # 5. Max action count stops further behavior
    sched3 = BehaviorScheduler(config=_SAFE_CONFIG)
    for _ in range(3):
        d = sched3.tick(force=True)
        if d["should_run"]:
            sched3.record_execution(d["action"])
            # Manually clear cooldown for test
            sched3.last_behavior_ts = 0.0
    d = sched3.tick(force=True)
    ok = not d["should_run"] and "max actions" in d["reason"]
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} max actions           → should_run={d['should_run']} reason='{d['reason']}'")
    passed += ok; failed += (not ok)

    # 6. Cooldown prevents immediate repeat
    sched4 = BehaviorScheduler(config=_SAFE_CONFIG)
    d1 = sched4.tick(force=True)
    if d1["should_run"]:
        sched4.record_execution(d1["action"])
    d2 = sched4.tick(force=True)
    ok = not d2["should_run"] and "cooldown" in d2["reason"]
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} cooldown              → second tick should_run={d2['should_run']} reason='{d2['reason'][:40]}'")
    passed += ok; failed += (not ok)

    # 7. Movement actions never appear in allowed list
    try:
        bad_cfg = dict(_SAFE_CONFIG)
        bad_cfg["allowed_actions"] = ["idle_flutter", "step_forward"]
        bad_cfg["weights"] = {"idle_flutter": 1.0, "step_forward": 1.0}
        sched5 = BehaviorScheduler(config=bad_cfg)
        for _ in range(20):
            d = sched5.tick(force=True)
            assert d["action"] != "step_forward", f"step_forward proposed!"
        ok = True
    except AssertionError:
        ok = False
    symbol = "✓" if ok else "✗"
    print(f"  {symbol} blocked_action filter → step_forward filtered from allowed list")
    passed += ok; failed += (not ok)

    total = passed + failed
    print(f"\n  Result: {'PASS' if failed == 0 else 'FAIL'} ({passed}/{total})\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
