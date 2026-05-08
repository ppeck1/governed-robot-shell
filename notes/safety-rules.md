# Safety Rules

## Shell Phase (current)

- Mode is `shell` by default.
- `movement_enabled` is `False` by default.
- `step_forward` is in the global blocked list regardless of mode allowlist.
- Locomotion is only possible in `mobile` mode with `movement_enabled = True`.
- Unknown actions fail closed — not approved, not partially executed.

## Fail-Closed Behavior

If an action is not recognized in the known action vocabulary, it is blocked.  
If the config file is missing or malformed, safe defaults apply.  
Safety must never silently pass an unknown action.

## Future Sensor Gates (Phase 4+)

Before locomotion is unblocked, the safety layer must additionally verify:
- distance sensor clear
- tilt/IMU within bounds
- battery voltage within range
- no thermal alarm
- emergency stop not active
- operator override present

## Doctrine

The safety layer is the most important module. Its job is not to be convenient —  
its job is to be the last line before the body does something irreversible.

## Hardware Backend Rules

- Mock backend is the default and always safe.
- Servo backend requires `"backend": "servo"` AND `"servo.enabled": true` in `config/body.json`.
- Missing or malformed config falls back to mock.
- Missing hardware libraries (adafruit_pca9685, board, busio) must fail safely — no crash.
- Servo angles must be bounded by per-channel `min_angle` / `max_angle` from config.
- Servo backend must not implement locomotion. `step_forward` is refused at the servo layer regardless of safety state.

## Servo Calibration Rules

- Calibration is disabled by default (`"enabled": false` in `config/body.json`).
- Calibration must be explicitly opted into. Do not enable until the servo is physically safe to move.
- Calibration uses narrower test angle ranges than the channel hardware bounds.
- Calibration will not run if hardware libraries are missing — it enters dry-run mode instead.
- Calibration is isolated: it does not connect to the planner, intent parser, safety layer, or body_controller.
- Calibration never includes locomotion actions.
- Re-disable calibration in config after a calibration session.

## Expression Servo Rules

- Servo backend is opt-in. Requires both `"backend": "servo"` and `"servo.enabled": true`.
- Expression actions must use named channels only — no raw channel numbers in action code.
- Angles must stay within per-channel `min_angle`/`max_angle` bounds from config.
- Channels return to home after each expression unless explicitly disabled in motion config.
- Locomotion (`step_forward`) is refused by the servo backend as a second layer of defense.
- Missing hardware libraries trigger dry-run mode, not a crash.

## Status Action Rules

- `report_status` is read-only and must not move hardware.
- It must still pass through the safety layer (present in all mode allowlists).
- It is dispatched directly to `print_status()`, never to the body backend.
- It may expose state and backend information only — no side effects.

## Camera Rules

- Camera is disabled by default (`"camera.enabled": false`).
- Camera capture is read-only — no capture action triggers body movement.
- Camera must fail safely if OpenCV is unavailable or device cannot be opened.
- No continuous monitoring in current phase.
- No autonomous interpretation in current phase.
- Camera actions pass through the safety layer like all other actions.

## Camera Diagnostic Rules

- Diagnostics are read-only — no frames saved during probe.
- Diagnostics must not open preview windows.
- Diagnostics must not trigger body movement.
- Capture metadata may be logged to JSONL, but no image interpretation occurs.
- Diagnostics report disabled state cleanly rather than attempting probe.

## Distance Sensor Rules

- Distance sensor is disabled by default.
- Sensor subsystem is observational only in current phase.
- Distance classification (safe/warning/critical) is informational — no automatic movement blocking yet.
- Sensor readings update `state.sensors` but do not trigger `body.execute_action()`.
- GPIO backend is not implemented; use mock backend for all current development.
- When sensor-aware safety gating is added (future phase), it must read from `state.sensors`, not directly from the sensor backend.

## Sensor-Aware Safety Rules

- Movement-class actions (currently: `step_forward`) check distance sensor gate.
- Critical distance status blocks movement-class actions.
- Warning distance status is informational only — movement allowed.
- Missing distance status allows movement by default (`unknown_blocks_movement: false`).
- Sensor gate runs after mode/movement_enabled check — shell mode still blocks first.
- Sensors constrain approval; they do not initiate actions.
- `movement_actions` list in `config/safety.json` controls which actions are gated.

## LLM Safety Rules

- LLM output is advisory only.
- LLM may only propose intents from `allowed_intents` in config.
- LLM may never emit actions, hardware commands, safety overrides, or state mutations.
- Proposals outside `allowed_intents` are rejected before reaching the planner.
- Proposals below `confidence_threshold` are rejected; rule intent used as fallback.
- Movement intent from LLM still flows through planner → safety → blocked in shell mode.
- LLM never calls body, sensor, perception, or safety directly.

## Ollama LLM Safety Rules

- Ollama backend is disabled by default.
- Ollama may only classify intent — no tools, no hardware calls.
- Response must be valid JSON: direct object or extractable from surrounding text.
- Arrays, bare strings, and malformed JSON are rejected.
- Intent must be in `allowed_intents` — validator rejects anything outside.
- Confidence must be in [0.0, 1.0] — out-of-range values rejected.
- LLMController vocabulary and confidence gates run after validation (defense in depth).
- Connection failures print reason and fall back to rule intent; shell continues.
- Servo commands or action names in Ollama output are rejected at vocabulary gate.

## Rule-First LLM Safety

- Strong non-idle rule intents bypass LLM arbitration entirely.
- LLM may only fill the gap when the rule parser returns `idle`.
- LLM output still passes vocabulary and confidence gates after arbitration.
- LLM may never override deterministic movement, status, or sensor commands.
- Planner and safety remain authoritative regardless of arbitration result.

## LLM Audit Rules

- Log LLM decision metadata for every classification call.
- Do not log raw prompts by default (Phase 5D).
- Do not log raw model responses by default (Phase 5D).
- Decision logs are observational only — they do not affect planner or safety.
- All five rejection reasons are recorded: `llm_disabled`, `rule_preferred`,
  `low_confidence`, `invalid_intent`, `backend_failure`.

## Behavioral Scheduler Safety Rules

- Scheduler disabled by default.
- Scheduler may only propose configured non-mobile actions.
- `step_forward` and all movement-prefixed actions are filtered at construction.
- Scheduled actions still pass through `check_safety()` before body execution.
- `force=True` tick bypasses idle threshold only — not cooldown, not safety.
- Scheduler must never call LLM, inspect sensors as goals, or create plans.
- Max action count prevents unbounded background execution.
