"""
LLM arbitration test utility — Phase 5C.

Proves rule-first behavior: strong rule intents skip the LLM.
Uses mock classifier so Ollama is not required.

Usage:
    python tools/test_llm_arbitration.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brain.intent import parse_intent
from brain.state import RobotState
from llm.llm_controller import LLMController
import llm.llm_controller as ctrl_mod


def make_controller_with_mock_enabled():
    """Return an LLMController with mock backend enabled, rules preferred."""
    orig = ctrl_mod._load_llm_config
    def patched():
        cfg = orig()
        cfg["enabled"] = True
        cfg["backend"] = "mock"
        cfg["prefer_rules_when_confident"] = True
        return cfg
    ctrl_mod._load_llm_config = patched
    c = LLMController()
    ctrl_mod._load_llm_config = orig
    return c


def run():
    llm   = make_controller_with_mock_enabled()
    state = RobotState()

    cases = [
        # (raw_input, expected_final, expect_used_llm, note)
        ("take a look",       "scan",            False, "strong rule → LLM skipped"),
        ("chirp",             "chirp",           False, "strong rule → LLM skipped"),
        ("come here",         "move",            False, "strong rule → LLM skipped"),
        ("status",            "status",          False, "strong rule → LLM skipped"),
        ("look around",       "scan",            False, "strong rule → LLM skipped"),
        # Mock classifier maps "how close is that" → distance_status with conf 0.80
        ("how close is that", "distance_status", True,  "idle rule → LLM fills gap"),
        # Mock classifier maps "take a photo" → capture_image with conf 0.79
        ("snap a picture",    "capture_image",   True,  "idle rule → LLM fills gap"),
        # Nonsense — mock returns idle/0.0, falls back to rule idle
        ("xyzzy nonsense",    "idle",            False, "idle rule → LLM no opinion → idle"),
    ]

    print("\n[LLM ARBITRATION TEST]\n")
    passed = failed = 0

    for raw, expected_final, expect_used, note in cases:
        rule_intent    = parse_intent(raw)
        classification = llm.classify_intent(raw, rule_intent, state)
        final          = classification["final_intent"]
        used           = classification["used_llm"]

        ok = (final == expected_final) and (used == expect_used)
        symbol = "✓" if ok else "✗"

        print(f"  {symbol} {raw!r:<28} rule={rule_intent:<16} "
              f"final={final:<16} used_llm={str(used):<5}  {note}")
        if not ok:
            print(f"      expected final='{expected_final}' used_llm={expect_used}")
            failed += 1
        else:
            passed += 1

    total = passed + failed
    print(f"\n  Result: {'PASS' if failed == 0 else 'FAIL'} ({passed}/{total})\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
