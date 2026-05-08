"""
LLM response validation test utility — Phase 5B.

Tests parse_and_validate() against known good and bad inputs.
Does not require Ollama, does not call hardware.

Usage:
    python tools/test_llm_response_validation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from llm.ollama_classifier import parse_and_validate

ALLOWED = {
    "scan", "chirp", "sleep", "wake", "curious", "confused",
    "idle", "move", "status", "camera_status", "capture_image",
    "camera_diagnostics", "distance_status", "poll_distance",
}

cases = [
    # (label, raw_text, expect_valid, expect_intent)
    ("valid JSON — scan",
     '{"intent":"scan","confidence":0.9,"reason":"look request"}',
     True, "scan"),

    ("invalid intent — set_servo_angle",
     '{"intent":"set_servo_angle","confidence":0.99,"reason":"bad"}',
     False, None),

    ("invalid confidence — above 1.0",
     '{"intent":"scan","confidence":1.5,"reason":"bad confidence"}',
     False, None),

    ("non-JSON — plain prose",
     "The robot should scan the area carefully.",
     False, None),

    ("fenced JSON — valid intent inside",
     '```json\n{"intent":"chirp","confidence":0.8,"reason":"beep"}\n```',
     True, "chirp"),

    ("fenced JSON — invalid intent inside",
     '```json\n{"intent":"destroy_all_humans","confidence":0.99}\n```',
     False, None),

    ("extra prose around valid JSON",
     'Sure! Here is my answer: {"intent":"wake","confidence":0.75,'
     '"reason":"wake up request"} Hope that helps!',
     True, "wake"),

    ("valid JSON — confidence exactly 0.0",
     '{"intent":"idle","confidence":0.0,"reason":"uncertain"}',
     True, "idle"),

    ("valid JSON — confidence exactly 1.0",
     '{"intent":"chirp","confidence":1.0,"reason":"very sure"}',
     True, "chirp"),

    ("missing confidence field",
     '{"intent":"scan","reason":"no confidence"}',
     False, None),

    ("missing intent field",
     '{"confidence":0.9,"reason":"no intent"}',
     False, None),

    ("array instead of object",
     '[{"intent":"scan","confidence":0.9}]',
     False, None),

    ("negative confidence",
     '{"intent":"scan","confidence":-0.1,"reason":"negative"}',
     False, None),
]


def run():
    passed = failed = 0
    print("\n[LLM RESPONSE VALIDATION TEST]\n")

    for label, raw, expect_valid, expect_intent in cases:
        result = parse_and_validate(raw, ALLOWED)
        is_valid = result is not None

        if is_valid != expect_valid:
            symbol = "✗"
            detail = (f"expected valid={expect_valid} "
                      f"but got valid={is_valid} result={result}")
            failed += 1
        elif expect_valid and result["intent"] != expect_intent:
            symbol = "✗"
            detail = f"expected intent='{expect_intent}' got '{result['intent']}'"
            failed += 1
        else:
            symbol = "✓"
            detail = (f"intent='{result['intent']}' conf={result['confidence']}"
                      if result else "rejected")
            passed += 1

        print(f"  {symbol} {label}")
        print(f"      → {detail}")

    print(f"\n  Result: {'PASS' if failed == 0 else 'FAIL'} "
          f"({passed}/{passed+failed})\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
