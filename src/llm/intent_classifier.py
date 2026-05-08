"""
Intent classifiers for the LLM layer.

All classifiers return the same shape:
  {
    "intent":     str,    # proposed intent from allowed vocabulary
    "confidence": float,  # 0.0 – 1.0
    "source":     str,    # classifier identifier
    "reason":     str,    # human-readable rationale
  }

The classifier NEVER returns actions, hardware commands, or state mutations.
It only proposes one intent from the allowed vocabulary.
"""

from typing import Optional


# ── Mock classifier ───────────────────────────────────────────────────────────

# Phrases the keyword rule parser may miss. Kept deliberately conservative.
# These are natural-language expansions only — no new capabilities.
_MOCK_PHRASE_MAP = {
    "what do you see":         ("camera_status",   0.75),
    "take a look":             ("scan",            0.78),
    "look at that":            ("scan",            0.76),
    "have a look":             ("scan",            0.74),
    "how close is that":       ("distance_status", 0.80),
    "how close am i":          ("distance_status", 0.80),
    "am i close":              ("distance_status", 0.77),
    "what's nearby":           ("distance_status", 0.73),
    "take a photo":            ("capture_image",   0.82),
    "snap a picture":          ("capture_image",   0.79),
    "come here":               ("move",            0.81),
    "follow me":               ("move",            0.72),
    "be quiet":                ("sleep",           0.76),
    "go to sleep":             ("sleep",           0.83),
    "wake up":                 ("wake",            0.85),
    "what's going on":         ("status",          0.74),
    "how are you doing":       ("status",          0.72),
    "are you okay":            ("status",          0.70),
    "you seem curious":        ("curious",         0.74),
    "that's interesting":      ("curious",         0.71),
}


class MockIntentClassifier:

    def classify(self, user_input: str,
                 context: Optional[dict] = None) -> dict:
        """
        Attempt to classify user_input against known natural phrases.
        Returns a classification dict. Confidence 0.0 signals no opinion.
        """
        text = user_input.lower().strip()

        for phrase, (intent, confidence) in _MOCK_PHRASE_MAP.items():
            if phrase in text:
                return {
                    "intent":     intent,
                    "confidence": confidence,
                    "source":     "mock_llm",
                    "reason":     f"Matched phrase: '{phrase}'",
                }

        return {
            "intent":     "idle",
            "confidence": 0.0,
            "source":     "mock_llm",
            "reason":     "No phrase match — mock classifier has no opinion.",
        }
