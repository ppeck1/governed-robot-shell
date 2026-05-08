"""
Session-scoped LLM intent controller — Phase 5D.

Arbitration order:
  A. LLM disabled          → rule_intent  (rejected_reason: llm_disabled)
  B. Strong rule intent     → rule_intent  (rejected_reason: rule_preferred)
  C. Idle / ambiguous       → call LLM
       vocab fail           → rule_intent  (rejected_reason: invalid_intent)
       confidence fail      → rule_intent  (rejected_reason: low_confidence)
       backend failure      → rule_intent  (rejected_reason: backend_failure)
       accepted             → llm_intent   (accepted: True)

Every classify_intent() call writes one record to the JSONL decision log
when decision logging is enabled.
"""

import json
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from brain.state import RobotState

PROJECT_ROOT      = Path(__file__).resolve().parents[2]
BODY_CONFIG_PATH  = PROJECT_ROOT / "config" / "body.json"

_DEFAULT_LLM_CONFIG = {
    "enabled":                    False,
    "backend":                    "mock",
    "confidence_threshold":       0.7,
    "fallback_to_rules":          True,
    "prefer_rules_when_confident": True,
    "rule_strong_intents": [
        "scan", "chirp", "sleep", "wake", "curious", "confused",
        "move", "status", "camera_status", "capture_image",
        "camera_diagnostics", "distance_status", "poll_distance",
    ],
    "allowed_intents": [
        "scan", "chirp", "sleep", "wake", "curious", "confused",
        "idle", "move", "status", "camera_status", "capture_image",
        "camera_diagnostics", "distance_status", "poll_distance",
    ],
    "ollama": {
        "base_url": "http://localhost:11434", "model": "llama3.2:3b",
        "timeout_seconds": 30, "temperature": 0.0,
        "top_p": 0.9, "max_context_chars": 1200,
    },
    "decision_logging": {
        "enabled": True,
        "log_path": "data/logs/llm_decisions.jsonl",
    },
}


def _load_llm_config() -> dict:
    try:
        cfg = json.loads(BODY_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("llm", _DEFAULT_LLM_CONFIG)
    except (FileNotFoundError, json.JSONDecodeError):
        return _DEFAULT_LLM_CONFIG


class LLMController:

    def __init__(self) -> None:
        cfg                      = _load_llm_config()
        self._enabled: bool      = cfg.get("enabled", False)
        self._backend: str       = cfg.get("backend", "mock")
        self._threshold: float   = float(cfg.get("confidence_threshold", 0.7))
        self._fallback: bool     = cfg.get("fallback_to_rules", True)
        self._prefer_rules: bool = cfg.get("prefer_rules_when_confident", True)
        self._strong: set        = set(cfg.get("rule_strong_intents",
                                                _DEFAULT_LLM_CONFIG["rule_strong_intents"]))
        self._allowed: set       = set(cfg.get("allowed_intents",
                                                _DEFAULT_LLM_CONFIG["allowed_intents"]))
        self._ollama_cfg         = cfg.get("ollama", _DEFAULT_LLM_CONFIG["ollama"])

        log_cfg                  = cfg.get("decision_logging", {})
        self._log_enabled: bool  = log_cfg.get("enabled", True)
        self._log_path: str      = log_cfg.get("log_path",
                                               "data/logs/llm_decisions.jsonl")

        self._classifier                     = None
        self.last_classification: Optional[dict] = None

        if self._enabled:
            self._classifier = self._load_classifier()
        else:
            print("[LLM] Intent classifier disabled.")

    # ── Classifier loading ────────────────────────────────────────────────────

    def _load_classifier(self):
        if self._backend == "mock":
            from llm.intent_classifier import MockIntentClassifier
            print("[LLM] Intent classifier enabled: mock")
            return MockIntentClassifier()
        if self._backend == "ollama":
            from llm.ollama_classifier import OllamaIntentClassifier
            model = self._ollama_cfg.get("model", "llama3.2:3b")
            print(f"[LLM] Intent classifier enabled: ollama model={model}")
            return OllamaIntentClassifier(self._ollama_cfg, list(self._allowed))
        print(f"[LLM] Unknown backend '{self._backend}' — using mock.")
        from llm.intent_classifier import MockIntentClassifier
        print("[LLM] Intent classifier enabled: mock (fallback)")
        return MockIntentClassifier()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _is_strong(self, rule_intent: str) -> bool:
        return (self._prefer_rules
                and rule_intent != "idle"
                and rule_intent in self._strong)

    def _make_result(self, final, rule, llm_intent=None, confidence=None,
                     used=False, reason="", rejected_reason=None) -> dict:
        return {
            "final_intent":    final,
            "rule_intent":     rule,
            "llm_intent":      llm_intent,
            "llm_confidence":  confidence,
            "used_llm":        used,
            "reason":          reason,
            "rejected_reason": rejected_reason,
        }

    def _write_log(self, user_input: str, result: dict) -> None:
        if not self._log_enabled:
            return
        from llm.decision_logger import log_llm_decision, make_record
        record = make_record(
            user_input       = user_input,
            rule_intent      = result["rule_intent"],
            llm_backend      = self._backend,
            llm_intent       = result["llm_intent"],
            llm_confidence   = result["llm_confidence"],
            final_intent     = result["final_intent"],
            used_llm         = result["used_llm"],
            accepted         = result["used_llm"] and
                               result["final_intent"] == result["llm_intent"],
            rejected_reason  = result.get("rejected_reason"),
            reason           = result["reason"],
        )
        log_llm_decision(record, self._log_path)

    # ── Public API ────────────────────────────────────────────────────────────

    def classify_intent(self, user_input: str, rule_intent: str,
                        state: Optional["RobotState"] = None) -> dict:

        # Case A: LLM disabled
        if not self._enabled or self._classifier is None:
            result = self._make_result(
                rule_intent, rule_intent,
                reason="LLM disabled.",
                rejected_reason="llm_disabled")
            self.last_classification = result
            self._write_log(user_input, result)
            return result

        # Case B: Strong rule intent — skip LLM
        if self._is_strong(rule_intent):
            print(f"[LLM] skipped — rule intent '{rule_intent}' preferred.")
            result = self._make_result(
                rule_intent, rule_intent,
                reason="Rule intent preferred.",
                rejected_reason="rule_preferred")
            self.last_classification = result
            self._write_log(user_input, result)
            return result

        # Case C: Idle / ambiguous — ask LLM
        context = None
        if state is not None:
            context = {
                "mode":             state.mode,
                "movement_enabled": state.movement_enabled,
                "sensors":          dict(state.sensors),
            }

        raw        = self._classifier.classify(user_input, context)
        llm_intent = raw.get("intent", "idle")
        confidence = float(raw.get("confidence", 0.0))
        source     = raw.get("source", "unknown")
        raw_reason = raw.get("reason", "")

        # Detect backend failure (idle/0.0 returned with error-like reason)
        backend_failed = (
            llm_intent == "idle" and confidence == 0.0
            and any(w in raw_reason.lower()
                    for w in ("error", "timeout", "failed", "refused", "invalid"))
        )

        if backend_failed:
            final = rule_intent if self._fallback else "idle"
            result = self._make_result(
                final, rule_intent, llm_intent, confidence, False,
                reason=raw_reason, rejected_reason="backend_failure")
            self.last_classification = result
            self._write_log(user_input, result)
            return result

        # Vocabulary gate
        if llm_intent not in self._allowed:
            final = rule_intent if self._fallback else "idle"
            print(f"[LLM] REJECTED intent='{llm_intent}' — not in allowed vocab.")
            result = self._make_result(
                final, rule_intent, llm_intent, confidence, False,
                reason=f"Rejected: not in allowed vocab. Falling back to '{final}'.",
                rejected_reason="invalid_intent")
            self.last_classification = result
            self._write_log(user_input, result)
            return result

        # Confidence gate
        if confidence < self._threshold:
            final = rule_intent if self._fallback else "idle"
            if confidence > 0.0:
                print(f"[LLM] LOW CONFIDENCE {confidence:.2f} for "
                      f"'{llm_intent}' — using rule intent '{final}'.")
            result = self._make_result(
                final, rule_intent, llm_intent, confidence, False,
                reason=f"Low confidence {confidence:.2f} < {self._threshold:.2f}.",
                rejected_reason="low_confidence")
            self.last_classification = result
            self._write_log(user_input, result)
            return result

        # Accepted
        print(f"[LLM] rule='{rule_intent}' → llm='{llm_intent}' "
              f"confidence={confidence:.2f} final='{llm_intent}'")
        result = self._make_result(
            llm_intent, rule_intent, llm_intent, confidence, True,
            reason=f"{source}: {raw_reason}",
            rejected_reason=None)
        self.last_classification = result
        self._write_log(user_input, result)
        return result

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        last = self.last_classification or {}
        status = {
            "llm_enabled":      self._enabled,
            "llm_backend":      self._backend,
            "llm_last_used":    last.get("used_llm"),
            "llm_last_intent":  last.get("final_intent"),
            "llm_last_confidence": last.get("llm_confidence"),
            "llm_last_reason":  last.get("reason"),
        }
        if self._log_enabled:
            status["llm_decision_log"] = self._log_path
        return status
