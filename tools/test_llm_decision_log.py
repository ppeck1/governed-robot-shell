"""
LLM decision log test utility — Phase 5D.

Proves JSONL logging is written for all cases:
  - rule_preferred
  - accepted (gap-fill)
  - low_confidence rejected
  - invalid_intent rejected
  - llm_disabled

Uses mock backend and a temporary log path. Does not modify
production config. Does not call planner, safety, or hardware.

Usage:
    python tools/test_llm_decision_log.py
"""

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from brain.state import RobotState
import llm.llm_controller as ctrl_mod
from llm.decision_logger import log_llm_decision, make_record

REQUIRED_FIELDS = {
    "timestamp", "user_input", "rule_intent", "llm_backend",
    "llm_intent", "llm_confidence", "final_intent",
    "used_llm", "accepted", "rejected_reason", "reason",
}


# ── Controller factory ────────────────────────────────────────────────────────

def make_controller(enabled: bool, log_path: str):
    """Build a controller with patched config pointing to test log."""
    orig = ctrl_mod._load_llm_config
    def patched():
        cfg = orig()
        cfg["enabled"]  = enabled
        cfg["backend"]  = "mock"
        cfg["prefer_rules_when_confident"] = True
        cfg["decision_logging"] = {"enabled": True, "log_path": log_path}
        return cfg
    ctrl_mod._load_llm_config = patched
    c = ctrl_mod.LLMController()
    ctrl_mod._load_llm_config = orig
    return c


# ── Log reader ────────────────────────────────────────────────────────────────

def read_log(path: str) -> list:
    p = Path(path)
    if not p.exists():
        return []
    records = []
    for line in p.read_text(encoding="utf-8").strip().splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


# ── Assertions ────────────────────────────────────────────────────────────────

def check_fields(record: dict, label: str) -> bool:
    missing = REQUIRED_FIELDS - set(record.keys())
    if missing:
        print(f"      missing fields: {missing}")
        return False
    return True


# ── Test runner ───────────────────────────────────────────────────────────────

def run():
    print("\n[LLM DECISION LOG TEST]\n")
    passed = failed = 0
    state  = RobotState()

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = str(Path(tmpdir) / "test_decisions.jsonl")

        # ── Case 1: LLM disabled ──────────────────────────────────────────────
        llm_off = make_controller(enabled=False, log_path=log_path)
        llm_off.classify_intent("chirp", "chirp", state)
        records = read_log(log_path)
        r = records[-1] if records else {}
        ok = (r.get("rejected_reason") == "llm_disabled"
              and check_fields(r, "llm_disabled"))
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} llm_disabled   → rejected_reason='{r.get('rejected_reason')}'")
        passed += ok; failed += (not ok)

        # ── Case 2: Rule preferred ────────────────────────────────────────────
        llm_on = make_controller(enabled=True, log_path=log_path)
        llm_on.classify_intent("take a look", "scan", state)
        records = read_log(log_path)
        r = records[-1]
        ok = (r.get("rejected_reason") == "rule_preferred"
              and r.get("final_intent") == "scan"
              and r.get("used_llm") == False
              and check_fields(r, "rule_preferred"))
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} rule_preferred → rejected_reason='{r.get('rejected_reason')}' "
              f"final='{r.get('final_intent')}'")
        passed += ok; failed += (not ok)

        # ── Case 3: Gap-fill accepted (mock: "how close is that" → distance_status 0.80)
        llm_on.classify_intent("how close is that", "idle", state)
        records = read_log(log_path)
        r = records[-1]
        ok = (r.get("accepted") == True
              and r.get("used_llm") == True
              and r.get("final_intent") == "distance_status"
              and r.get("rejected_reason") is None
              and check_fields(r, "accepted"))
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} gap_fill       → accepted={r.get('accepted')} "
              f"final='{r.get('final_intent')}'")
        passed += ok; failed += (not ok)

        # ── Case 4: Low confidence — inject a low-conf classifier ─────────────
        class LowConfClassifier:
            def classify(self, t, ctx=None):
                return {"intent": "scan", "confidence": 0.1,
                        "source": "test", "reason": "test low conf"}
        llm_on._classifier = LowConfClassifier()
        llm_on.classify_intent("vague thing", "idle", state)
        records = read_log(log_path)
        r = records[-1]
        ok = (r.get("rejected_reason") == "low_confidence"
              and r.get("used_llm") == False
              and check_fields(r, "low_confidence"))
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} low_confidence → rejected_reason='{r.get('rejected_reason')}'")
        passed += ok; failed += (not ok)

        # ── Case 5: Invalid intent ────────────────────────────────────────────
        class BadIntentClassifier:
            def classify(self, t, ctx=None):
                return {"intent": "set_servo_angle", "confidence": 0.95,
                        "source": "test", "reason": "injection attempt"}
        llm_on._classifier = BadIntentClassifier()
        llm_on.classify_intent("set servo 0 to 90", "idle", state)
        records = read_log(log_path)
        r = records[-1]
        ok = (r.get("rejected_reason") == "invalid_intent"
              and r.get("used_llm") == False
              and check_fields(r, "invalid_intent"))
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} invalid_intent → rejected_reason='{r.get('rejected_reason')}' "
              f"llm_intent='{r.get('llm_intent')}'")
        passed += ok; failed += (not ok)

        # ── JSONL validity check ───────────────────────────────────────────────
        all_records = read_log(log_path)
        jsonl_ok = len(all_records) >= 5
        fields_ok = all(REQUIRED_FIELDS.issubset(rec.keys()) for rec in all_records)
        ok = jsonl_ok and fields_ok
        symbol = "✓" if ok else "✗"
        print(f"\n  {symbol} jsonl_valid    → {len(all_records)} records, "
              f"all fields present: {fields_ok}")
        passed += ok; failed += (not ok)

    total = passed + failed
    print(f"\n  Result: {'PASS' if failed == 0 else 'FAIL'} ({passed}/{total})\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
