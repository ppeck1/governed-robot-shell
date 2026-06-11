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

## 2026-06-09 - Phase 3F / Sim S0-S3 Virtual Environment

- Added `RobotRuntime` as the shared governed command path for CLI and API.
- Added deterministic simulator modules under `src/sim/`.
- Added `backend = "sim"` support to `BodyController`; default `config/body.json` remains `"backend": "mock"`.
- Added FastAPI simulator app at `src/sim_api.py`.
- Added static local dashboard under `src/sim_static/` with command controls, sensor/status panels, event log, and 3D-style canvas view.
- Added deterministic scenarios for boot/status, chirp, scan, curious/confused, sleep/wake, blocked walk, and obstacle probe.
- Added structured JSONL logging at `data/logs/robot_events.jsonl`.
- Added pytest coverage for pipeline, safety, sim backend, scenario replay, API routes, and dashboard hooks.
- No hardware movement added. Locomotion remains blocked in shell mode and refused by the sim backend.

## 2026-06-09 - Phase 3G / Sim S4-S7 Governed Replay and Proposals

- Added `utils/events.py` with a single append-only kernel event writer.
- Added event export and replay support through `RobotRuntime`.
- Added `/sim/events`, `/sim/export`, `/sim/replay`, `/sim/manifest`, `/sim/readiness`, and proposal queue endpoints.
- Added emergency stop and motion inhibit fields to `RobotState`.
- Added sensor-aware movement safety: mobile movement now also needs sufficient `front_clearance`.
- Added finite emergency actions: `set_emergency_stop`, `clear_emergency_stop`.
- Added manifest/readiness helpers and review-only proposal queue.
- Dashboard now includes safety gate, readiness, replay/export, and proposal preview panels.
- Test suite expanded to 18 passing.
- No autonomous learning, LLM provider, or hardware movement added.

## 2026-06-09 - Phase 3H Action Registry and Nonverbal Cues

- Added `brain/action_registry.py` with one code-level registry for planner action metadata.
- Added `body/audio_cues.py` with chirp-only symbolic cue ids.
- Added `CommandEnvelope` support to `RobotRuntime`.
- Safety now uses registry metadata for known actions, mode checks, movement requirements, emergency-stop behavior, and selected cue.
- Mock backend prints cue ids through `[MOCK CUE] ...`.
- Sim backend records `latest_audio_cue`, `audio_state`, and `cue_count`.
- Preview commands evaluate parser/planner/safety without executing body actions or cue output.
- Test suite expanded to 27 passing.
- No speech, STT, TTS, wake word, real audio hardware, or locomotion behavior added.
