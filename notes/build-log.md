# Build Log

## 2026-05-06 — Phase 1 initial build

- CLI, intent parser (keyword), planner, mock body, safety blocklist, logger wired.
- Tested: `chirp` (approved), `walk forward` (blocked).
- Both entries visible in `data/logs/robot.log`.
- All note files blank at this point.

## 2026-05-08 — Phase 2 begin

- `CLAUDE.md` created at repo root as persistent build memory.
- `RobotState` dataclass implemented in `src/brain/state.py`.
- `config/safety.json` created with mode-aware action allowlists.
- `src/body/safety.py` updated: loads config, state-aware, fails closed on unknown actions.
- `src/brain/intent.py` expanded with broader keyword coverage.
- `src/brain/planner.py` expanded: full action vocabulary, unknown → idle_flutter.
- `src/body/mock_body.py` expanded: descriptive per-action mock output.
- `src/main.py` updated: instantiates RobotState, passes state into safety, updates after execution.
- All documentation files filled.

Next target: Phase 3 — single servo expression via PCA9685.

## 2026-05-08 — Phase 2.1 Cleanup

- Fixed logger path: `PROJECT_ROOT = Path(__file__).resolve().parents[2]`
- Removed accidental `src/data/logs/robot.log` created by running from `src/`
- Confirmed single log at `data/logs/robot.log` regardless of invocation directory

## Phase 2.1 Smoke Test

Commands tested:

```
chirp
look around
act curious
huh
flutter
walk forward
quit
```

Results:
- expressive actions approved ✓
- `walk forward` blocked ✓
- log written to root `data/logs/robot.log` ✓
- no `src/data/` created ✓

Next: Phase 3 — single servo expression via PCA9685.

## 2026-05-08 — Phase 3A Servo Backend Skeleton

- `config/body.json` created. Default backend: mock.
- `src/body/body_controller.py` created. Reads config, selects backend.
- `src/body/servo_body.py` created. PCA9685 scaffold, safe import handling, locomotion refused.
- `src/main.py` updated to use `body_controller.execute_action`.
- Acceptance test passed: all expression actions mock, walk forward blocked, log at root.

## 2026-05-08 — Phase 3B Servo Calibration Mode

- `config/body.json` updated with `calibration` block (disabled by default).
- `tools/calibrate_servo.py` created: isolated REPL, refuses when disabled, dry-runs without hardware.
- `move_named_servo()` helper added to `servo_body.py`.
- Acceptance tests: mock robot unchanged ✓, calibration refused when disabled ✓, dry-run on missing hardware ✓.

Next: Phase 3C — enable servo backend and connect expression actions to real channels.

## 2026-05-08 — Phase 3C Expression Servo Integration

- `servo_body.py` rewritten with full expression action implementations.
- `body_controller.py` strengthened: reports backend once, handles all fallback cases.
- `config/body.json` updated with `motion` block.
- Test 1 (mock default): all expression actions mock-only ✓
- Test 2 (servo, no hardware): dry-run mode, angles/pulses printed ✓, walk forward blocked ✓, no crash ✓

Note: ServoBody is currently re-instantiated on each execute_action call.
This is fine for Phase 3C but produces repeated dry-run warnings in servo mode.
Phase 3D should lift ServoBody to a persistent session-level instance.

Next: Phase 3D — persistent servo session, then Phase 4 sensors.

## 2026-05-08 — Phase 3D Persistent Body Controller

- `BodyController` class replaces module-level function.
- Config loaded once at `__init__`. Backend message printed once at startup.
- `ServoBody` instantiated once; hardware warning appears once per session.
- `self.positions` added to `ServoBody`; updated on every `_write` call.
- `get_positions()` / `get_servo_positions()` available for future state integration.
- Test 1 (mock): backend line printed once ✓
- Test 2 (servo dry-run): init warning once, not per action ✓, walk forward blocked ✓

Next: Phase 4 sensors, or Phase 3E if real hardware testing needs a patch first.

## 2026-05-08 — Phase 3E Status and Observability

- `status` intent added; maps to `report_status` action.
- `report_status` added to all safety mode allowlists.
- `BodyController.get_status()` added.
- `print_status()` helper in `main.py` — read-only, no hardware call.
- Test 1 (mock): status updates last_intent/last_action correctly ✓
- Test 2 (servo dry-run): status shows servo_ready=False, positions after action ✓

Behavior note: status after a blocked action shows the previous approved
last_intent/last_action (the blocked action does not update state).
This is correct and consistent — blocked actions produce no state change.

Next: Phase 4 sensors, or real hardware session if PCA9685 is ready.

## 2026-05-08 — Phase 4A Camera/Perception Scaffold

- `src/perception/` created with `camera.py` and `perception_controller.py`.
- `data/captures/` directory created.
- OpenCV: installed in build environment; no physical webcam present.
- Camera enabled, device 0: initialized but not ready (no device) — safe failure ✓
- Camera disabled: capture refused cleanly ✓
- `capture_camera_frame` and `report_camera_status` added to all safety allowlists.
- Status command now includes camera fields.

**Bug fixed during build:** `parents[3]` in camera.py and perception_controller.py
was one level too deep — changed to `parents[2]` to correctly resolve project root.

Next: Phase 4B distance/touch sensors, or real hardware session.

## 2026-05-08 — Phase 4B Camera Diagnostics and Metadata

- `run_camera_diagnostics` action added; routed to `PerceptionController`.
- `Camera.run_diagnostics()` probes indices [0,1,2] — no saves, no previews.
- `Camera.capture_frame()` records metadata on both success and failure.
- Metadata JSONL log: `data/captures/capture_log.jsonl` (project-root-relative).
- Status now includes: camera_device, last_capture_ok, last_capture_size.
- Test 1 (disabled): all camera commands safe ✓
- Test 2 (enabled, no webcam): diagnostics show 3 probed indices as unopened ✓;
  failed capture metadata correctly stored ✓; shell continues ✓

Note: OpenCV V4L2/FFMPEG warnings on stderr are expected when no /dev/video* exists.
They are not errors — the shell continues cleanly.

## 2026-05-08 — Phase 4C Distance Sensor Scaffold

- `src/sensors/` created with `distance_sensor.py` and `sensor_controller.py`.
- `SensorController(state)` instantiated at startup with RobotState reference.
- Mock backend tested at 100 cm (safe), 25 cm (warning), 10 cm (critical).
- All classifications correct; `state.sensors` populated on each poll.
- `status` command shows distance fields from live state.sensors dict.
- No hardware GPIO implemented — mock only.

Next: Phase 5 LLM intent layer, or Phase 4D touch/tilt sensors, or real hardware session.

## 2026-05-08 — Phase 4D Sensor-Aware Safety Gate

- `safety.py` refactored with 5-step evaluation order.
- `is_movement_action()` and `check_sensor_gates()` helpers added.
- `config/safety.json` updated with `movement_actions` and `sensor_gates`.
- `tools/test_sensor_safety.py` created — 7/7 PASS:
  - safe (30.1 cm)    → approved ✓
  - warning (20 cm)   → approved ✓
  - critical (10 cm)  → blocked  ✓
  - missing           → approved ✓
  - full gate mobile/no-sensor → approved ✓
  - full gate mobile/critical  → blocked  ✓
  - shell mode/safe sensor     → blocked (mode gate) ✓
- Normal shell behavior unchanged.

Next: Phase 5 LLM intent layer, or real hardware session.

## 2026-05-08 — Phase 5A LLM Intent Classifier Scaffold

- `src/llm/` created.
- `MockIntentClassifier`: ~20 natural phrases mapped to allowed intents.
- `LLMController`: vocabulary gate, confidence threshold, fallback-to-rules logic.
- Disabled default: rule parser behavior unchanged ✓
- Mock enabled: "take a look" → scan, "how close is that" → distance_status ✓
- "come here" → move → step_forward → safety blocked ✓
- Invalid intent "set_servo_angle" → rejected ✓
- Low confidence 0.2 → fallback to rule intent ✓
- Status shows llm_enabled, llm_backend, llm_last_used, llm_last_intent, confidence ✓

Next: Phase 5B — real API backend (Anthropic/OpenAI/Ollama), or Phase 5B prompt hardening.

## 2026-05-08 — Phase 5B Local Ollama Intent Backend

- `src/llm/ollama_classifier.py` created; standard library HTTP only.
- `tools/test_llm_response_validation.py`: 13/13 PASS.
  - Bug caught during build: regex was extracting `{...}` from inside arrays.
  - Fix: try `json.loads()` first; reject if array before attempting regex.
- `tools/test_ollama_classifier.py` created for live Ollama testing.
- Test A (disabled): behavior unchanged ✓
- Test B (mock): still works ✓
- Test C (validation): 13/13 PASS ✓
- Test D (ollama, no server): connection refused → fallback → shell continues ✓
- Test E (ollama live): requires Ollama running locally with llama3.2:3b pulled.

## 2026-05-08 — Phase 5C Ollama Tuning and Rule-First Arbitration

- Rule-first arbitration implemented; `prefer_rules_when_confident` config flag.
- Ollama timeout → 30 s; timeout handled cleanly, no stack traces.
- Prompt strengthened with 14 canonical examples.
- `tools/test_llm_arbitration.py`: 8/8 PASS.
  - Strong intents (scan, chirp, move, status): LLM skipped ✓
  - idle + mock match (how close is that): LLM used ✓
  - idle + no match (xyzzy): fallback idle ✓
- `tools/warm_ollama.py` created for pre-session model warm-up.
- `tools/test_ollama_classifier.py` updated with per-prompt timing.
- Test D (Ollama unavailable): `[LLM] Ollama classify failed: ...` → fallback ✓

## 2026-05-08 — Phase 5D LLM Decision Logging

- `src/llm/decision_logger.py` created.
- `LLMController` writes one JSONL record per classify_intent() call.
- `tools/test_llm_decision_log.py`: 6/6 PASS:
  - llm_disabled ✓, rule_preferred ✓, gap_fill accepted ✓,
    low_confidence ✓, invalid_intent ✓, jsonl_valid ✓
- Status shows `llm_decision_log` path when logging enabled.
- Production log: `data/logs/llm_decisions.jsonl`

Next: Phase 5E (transcript logging), or Phase 6 (movement/locomotion).

## 2026-05-08 — Phase 6A Behavioral Scheduler Scaffold

- `src/behavior/behavior_scheduler.py` created.
- `log_event()` updated with optional `source` parameter (backward-compatible).
- `tools/test_behavior_scheduler.py`: 7/7 PASS.
  - Note: 50-instance locomotion test prints scheduler init message 50 times.
  - This is noisy but harmless — consider a `quiet=True` init param in future cleanup.
- `tools/test_behavior_safety.py`: 5/5 PASS.
- Test A (disabled): behavior fields in status ✓, tick returns no-action ✓
- Test B (enabled): first forced tick proposes action ✓, second blocked by cooldown ✓

Next: Phase 6B (threading / background tick), or Phase 6C (locomotion enable sequence).
