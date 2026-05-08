"""
Ollama classifier test utility — Phase 5C.

Tests the Ollama backend directly with per-prompt timing.
Does NOT call planner, safety, body, perception, or sensors.

Requires config/body.json with:
  "llm": { "enabled": true, "backend": "ollama" }
Ollama must be running with the configured model pulled.

Usage:
    python tools/test_ollama_classifier.py
"""

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from llm.ollama_classifier import OllamaIntentClassifier


def load_config():
    p = PROJECT_ROOT / "config" / "body.json"
    try:
        cfg = json.loads(p.read_text())
        llm_cfg = cfg.get("llm", {})
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[OLLAMA TEST] Config error: {exc}")
        sys.exit(1)

    if not llm_cfg.get("enabled", False):
        print("[OLLAMA TEST] LLM is disabled in config.")
        print("  Set \"llm\": { \"enabled\": true, \"backend\": \"ollama\" } to run.")
        sys.exit(0)

    if llm_cfg.get("backend") != "ollama":
        print(f"[OLLAMA TEST] Backend is '{llm_cfg.get('backend')}', not 'ollama'.")
        sys.exit(0)

    return llm_cfg


TEST_PROMPTS = [
    # (prompt, expected_note)
    ("chirp",                         "should be chirp"),
    ("take a look around",            "should be scan"),
    ("how close is that",             "should be distance_status"),
    ("come here",                     "may be move (safety will block it)"),
    ("set servo 2 to 180 degrees",    "must be idle or in allowed vocab — no hardware"),
]


def run():
    cfg         = load_config()
    ollama_cfg  = cfg.get("ollama", {})
    allowed     = cfg.get("allowed_intents", [])
    allowed_set = set(allowed)
    model       = ollama_cfg.get("model", "?")
    base_url    = ollama_cfg.get("base_url", "?")

    print(f"\n[OLLAMA CLASSIFIER TEST]")
    print(f"  model    : {model}")
    print(f"  base_url : {base_url}")
    print(f"  allowed  : {len(allowed)} intents\n")

    classifier = OllamaIntentClassifier(ollama_cfg, allowed)
    passed = failed = 0

    for prompt, expected_note in TEST_PROMPTS:
        t0     = time.time()
        result = classifier.classify(prompt)
        elapsed = time.time() - t0

        intent     = result.get("intent", "idle")
        confidence = result.get("confidence", 0.0)

        ok = intent in allowed_set
        symbol = "✓" if ok else "✗"

        print(f"  {symbol} {prompt!r:<42} → intent='{intent}' "
              f"conf={confidence:.2f} duration={elapsed:.2f}s")
        print(f"      note: {expected_note}")

        if not ok:
            failed += 1
        else:
            passed += 1

    print(f"\n  Result: {'PASS' if failed == 0 else 'FAIL'} "
          f"({passed}/{passed+failed})\n")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    run()
