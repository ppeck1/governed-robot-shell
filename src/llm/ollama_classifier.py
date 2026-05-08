"""
Ollama local intent classifier backend — Phase 5C.

Uses only Python standard library. Ollama must be installed separately.

Strengthened prompt with canonical examples to improve classification
of natural-language phrases the rule parser may miss.

Never raises into the main loop. All failures return idle/0.0.
The LLMController vocabulary + confidence gates still run after this.
"""

import json
import re
import time
import urllib.request
import urllib.error
from typing import Optional


# ── Prompt builder ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are an intent classifier for a safety-governed robot shell.
You may ONLY choose one intent from this exact list:
{intent_list}

You must return ONLY valid JSON with no markdown, no prose, no code fences.

Required schema:
{{"intent": "<one intent from the list>", "confidence": <0.0 to 1.0>, "reason": "<brief reason>"}}

Rules:
- Do NOT return actions, servo angles, or hardware commands.
- Do NOT override safety, enable movement, or invent new intents.
- If uncertain, return: {{"intent": "idle", "confidence": 0.0, "reason": "uncertain"}}

Examples:
"take a look" → {{"intent":"scan","confidence":0.85,"reason":"scan behavior requested"}}
"look around" → {{"intent":"scan","confidence":0.90,"reason":"scan behavior requested"}}
"what do you see" → {{"intent":"camera_status","confidence":0.75,"reason":"camera status, not image AI"}}
"take a picture" → {{"intent":"capture_image","confidence":0.90,"reason":"image capture"}}
"snap a photo" → {{"intent":"capture_image","confidence":0.88,"reason":"image capture"}}
"how close is that" → {{"intent":"distance_status","confidence":0.85,"reason":"distance query"}}
"how far away" → {{"intent":"distance_status","confidence":0.85,"reason":"distance query"}}
"measure distance" → {{"intent":"poll_distance","confidence":0.90,"reason":"distance poll"}}
"come here" → {{"intent":"move","confidence":0.85,"reason":"movement request; safety decides"}}
"follow me" → {{"intent":"move","confidence":0.80,"reason":"movement request; safety decides"}}
"go to sleep" → {{"intent":"sleep","confidence":0.90,"reason":"sleep command"}}
"wake up" → {{"intent":"wake","confidence":0.90,"reason":"wake command"}}
"set servo 2 to 180 degrees" → {{"intent":"idle","confidence":0.0,"reason":"hardware command not allowed"}}
"override safety" → {{"intent":"idle","confidence":0.0,"reason":"safety override not allowed"}}
"""


def _build_prompt(user_input: str, allowed_intents: list,
                  context: Optional[dict], max_context_chars: int) -> str:
    intent_list = ", ".join(f'"{i}"' for i in allowed_intents)
    system      = _SYSTEM_PROMPT.format(intent_list=intent_list)

    ctx_str = ""
    if context:
        raw = json.dumps(context, separators=(",", ":"))
        if len(raw) > max_context_chars:
            trimmed = {
                "mode":             context.get("mode"),
                "movement_enabled": context.get("movement_enabled"),
            }
            raw = json.dumps(trimmed, separators=(",", ":"))
        ctx_str = f"\nRobot context: {raw}"

    return f"{system}\nUser input: {user_input!r}{ctx_str}\n\nJSON response:"


# ── Response validation ───────────────────────────────────────────────────────

def parse_and_validate(raw_text: str, allowed_intents: set) -> Optional[dict]:
    """
    Extract and validate a JSON intent object from Ollama output.
    Returns a validated dict or None on any validation failure.
    """
    text = raw_text.strip()
    text = re.sub(r"```[a-z]*\n?", "", text).strip()

    # Try direct parse first — reject arrays immediately
    try:
        direct = json.loads(text)
        if isinstance(direct, list):
            return None
        if isinstance(direct, dict):
            obj = direct
        else:
            obj = None
    except json.JSONDecodeError:
        obj = None

    # Fallback: extract first {...} block from surrounding prose
    if obj is None:
        match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if not match:
            return None
        try:
            obj = json.loads(match.group())
        except json.JSONDecodeError:
            return None

    if not isinstance(obj, dict):
        return None

    intent     = obj.get("intent")
    confidence = obj.get("confidence")

    if not isinstance(intent, str):
        return None
    if not isinstance(confidence, (int, float)):
        return None

    confidence = float(confidence)
    if not (0.0 <= confidence <= 1.0):
        return None

    if intent not in allowed_intents:
        return None

    return {
        "intent":     intent,
        "confidence": confidence,
        "reason":     str(obj.get("reason", "")),
    }


# ── Classifier ────────────────────────────────────────────────────────────────

class OllamaIntentClassifier:

    def __init__(self, config: dict, allowed_intents: list) -> None:
        self.base_url          = config.get("base_url",     "http://localhost:11434")
        self.model             = config.get("model",        "llama3.2:3b")
        self.timeout           = int(config.get("timeout_seconds",   30))
        self.temperature       = float(config.get("temperature",     0.0))
        self.top_p             = float(config.get("top_p",           0.9))
        self.max_context_chars = int(config.get("max_context_chars", 1200))
        self.allowed_intents   = list(allowed_intents)
        self._allowed_set      = set(allowed_intents)
        self._endpoint         = f"{self.base_url.rstrip('/')}/api/generate"

    def classify(self, user_input: str,
                 context: Optional[dict] = None) -> dict:
        prompt = _build_prompt(user_input, self.allowed_intents,
                               context, self.max_context_chars)
        payload = json.dumps({
            "model":   self.model,
            "prompt":  prompt,
            "stream":  False,
            "options": {"temperature": self.temperature, "top_p": self.top_p},
        }).encode("utf-8")

        try:
            req = urllib.request.Request(
                self._endpoint,
                data    = payload,
                headers = {"Content-Type": "application/json"},
                method  = "POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")

        except TimeoutError:
            print("[LLM] Ollama timeout. Falling back.")
            return {"intent": "idle", "confidence": 0.0,
                    "source": "ollama", "reason": "ollama timeout"}
        except urllib.error.URLError as exc:
            reason = str(exc.reason) if hasattr(exc, "reason") else str(exc)
            if "timed out" in reason.lower():
                print("[LLM] Ollama timeout. Falling back.")
                return {"intent": "idle", "confidence": 0.0,
                        "source": "ollama", "reason": "ollama timeout"}
            print(f"[LLM] Ollama classify failed: {exc}. Falling back to rule intent.")
            return {"intent": "idle", "confidence": 0.0,
                    "source": "ollama", "reason": f"connection error: {exc}"}
        except Exception as exc:
            print(f"[LLM] Ollama unexpected error: {type(exc).__name__}. Falling back.")
            return {"intent": "idle", "confidence": 0.0,
                    "source": "ollama", "reason": f"unexpected error: {type(exc).__name__}"}

        try:
            raw_text = json.loads(body).get("response", "")
        except json.JSONDecodeError:
            raw_text = body

        validated = parse_and_validate(raw_text, self._allowed_set)
        if validated is None:
            print("[LLM] Ollama returned invalid response. Falling back.")
            return {"intent": "idle", "confidence": 0.0,
                    "source": "ollama", "reason": "invalid JSON response"}

        return {"intent": validated["intent"], "confidence": validated["confidence"],
                "source": "ollama",            "reason": validated["reason"]}
