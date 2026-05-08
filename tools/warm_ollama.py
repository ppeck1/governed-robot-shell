"""
Ollama warmup utility — Phase 5C.

Sends one simple classification to Ollama to trigger model load.
Reduces first-call latency during live sessions.

Usage:
    python tools/warm_ollama.py

Does not call planner, safety, body, perception, or sensors.
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
        return cfg.get("llm", {})
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[OLLAMA WARMUP] Config error: {exc}")
        sys.exit(1)


def run():
    cfg         = load_config()
    ollama_cfg  = cfg.get("ollama", {})
    allowed     = cfg.get("allowed_intents", ["idle"])
    model       = ollama_cfg.get("model", "llama3.2:3b")
    base_url    = ollama_cfg.get("base_url", "http://localhost:11434")

    print(f"\n[OLLAMA WARMUP]")
    print(f"  model    : {model}")
    print(f"  base_url : {base_url}")

    classifier = OllamaIntentClassifier(ollama_cfg, allowed)

    t0     = time.time()
    result = classifier.classify("chirp")
    elapsed = time.time() - t0

    intent     = result.get("intent", "?")
    confidence = result.get("confidence", 0.0)
    reason     = result.get("reason", "")

    if intent == "idle" and confidence == 0.0 and "error" in reason.lower():
        print(f"  [OLLAMA WARMUP] failed: {reason}")
    else:
        print(f"  response_time_seconds : {elapsed:.2f}")
        print(f"  intent                : {intent}")
        print(f"  confidence            : {confidence:.2f}")
        print(f"  reason                : {reason}")

    print()


if __name__ == "__main__":
    run()
