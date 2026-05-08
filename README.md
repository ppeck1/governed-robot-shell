# LLM Robot Shell

A governed robot-control shell. Language input is compressed into intent,
validated by a safety layer, and only then executed by the body or perception
subsystem. No LLM directly controls hardware.

## Current Phase

**Phase 4A** — Camera/perception scaffold.
No real hardware is enabled by default. All actions are safe.

## How to Run

```bash
cd src
python main.py
```

## Dependencies

Core shell: no external dependencies.

Camera support (optional):
```bash
pip install opencv-python
```

Servo support (future, Raspberry Pi only):
```bash
pip install adafruit-circuitpython-pca9685 adafruit-circuitpython-motor
```

## Example Commands

| Command         | Intent         | Action                  | Result   |
|-----------------|----------------|-------------------------|----------|
| chirp           | chirp          | play_chirp              | approved |
| look around     | scan           | head_turn_left_right    | approved |
| act curious     | curious        | express_curious         | approved |
| flutter         | idle           | idle_flutter            | approved |
| wake            | wake           | wake                    | approved |
| sleep           | sleep          | sleep                   | approved |
| status          | status         | report_status           | approved |
| camera status   | camera_status  | report_camera_status    | approved |
| capture image   | capture_image  | capture_camera_frame    | approved |
| camera status   | camera_status  | report_camera_status    | approved |
| camera diag     | camera_diag    | run_camera_diagnostics  | approved |
| walk forward    | move           | step_forward            | blocked  |
| quit            | —              | —                       | exits    |

## Enabling Camera

In `config/body.json`:
```json
"camera": {
  "enabled": true,
  "device_index": 0
}
```

Requires `pip install opencv-python`. Camera must be connected.
Captures save to `data/captures/capture_YYYYMMDD_HHMMSS.jpg`.

## Safety Notes

- Movement (`step_forward`) is blocked in shell mode.
- Servo backend is disabled by default; requires explicit config opt-in.
- Camera is disabled by default; requires explicit config opt-in.
- Camera capture never triggers servo movement.
- Logs are written to `data/logs/robot.log`.

## Logs

All decisions are written to `data/logs/robot.log`.

## Camera Diagnostics

Probe available webcam indices without capturing:

```
camera diagnostics
```

Output shows which device indices are available and their reported dimensions.
Useful for identifying the correct `device_index` before enabling capture.

## Capture Metadata Log

When `camera.diagnostics.save_metadata` is true, each capture attempt
(success or failure) is appended to:

```
data/captures/capture_log.jsonl
```

One JSON object per line. Useful for auditing hardware testing sessions.

## Sensor Subsystem

Distance sensor provides environmental state input to the robot.

Enable mock sensor in `config/body.json`:
```json
"distance_sensor": {
  "enabled": true,
  "backend": "mock",
  "mock_distance_cm": 100.0,
  "warning_distance_cm": 30.0,
  "critical_distance_cm": 15.0
}
```

| Command          | Intent           | Action                  |
|------------------|------------------|-------------------------|
| poll distance    | poll_distance    | poll_distance_sensor    |
| distance status  | distance_status  | report_distance_status  |

Distance classifications:
- `safe`     — above warning threshold
- `warning`  — between critical and warning threshold
- `critical` — at or below critical threshold

Sensor readings are informational only. No movement is triggered automatically.

**Future GPIO support:** when a real HC-SR04 sensor is connected, set `"backend": "gpio"` and configure `trigger_pin` and `echo_pin`. GPIO backend is not yet implemented.

## Sensor-Aware Safety

Distance sensor readings now constrain movement-class actions through the safety gate.

Classification → safety effect:
- `safe`     — movement allowed
- `warning`  — movement allowed (informational only in current phase)
- `critical` — movement blocked

In the current default shell mode, locomotion is blocked by the mode gate before the sensor gate is reached. The sensor gate is active and proven — it applies when `mode=mobile` and `movement_enabled=True` are set in future phases.

Run the sensor safety test utility:
```bash
python tools/test_sensor_safety.py
```

## Optional LLM Intent Classifier

The project includes an optional LLM intent classifier scaffold. Disabled by default.

Enable in `config/body.json`:
```json
"llm": {
  "enabled": true,
  "backend": "mock",
  "confidence_threshold": 0.7,
  "fallback_to_rules": true
}
```

When enabled, the classifier may propose an intent from the finite allowed vocabulary.
Proposals outside the vocabulary or below the confidence threshold are rejected.
The existing planner and safety system remain authoritative.

The LLM never emits actions, modifies state, or bypasses safety.

## Local Ollama Intent Backend

The shell can optionally use a local Ollama model as an intent classifier. Disabled by default.

Install Ollama and pull a model:
```bash
ollama pull llama3.2:3b
ollama serve
```

Enable in `config/body.json`:
```json
"llm": {
  "enabled": true,
  "backend": "ollama"
}
```

The model may only propose one intent from the allowed vocabulary.
Responses are validated strictly: wrong intent names, out-of-range confidence,
malformed JSON, and arrays are all rejected before the planner is reached.
Planner and safety remain authoritative.

No additional pip packages required — Ollama communication uses the standard library.

Test the validator without Ollama:
```bash
python tools/test_llm_response_validation.py
```

Test Ollama live (requires Ollama running):
```bash
python tools/test_ollama_classifier.py
```

## LLM Tools

```bash
# Warm up Ollama model before a live session (reduces first-call latency)
python tools/warm_ollama.py

# Test arbitration logic without Ollama (uses mock)
python tools/test_llm_arbitration.py

# Test Ollama live with timing (requires Ollama running)
python tools/test_ollama_classifier.py

# Validate response parsing without Ollama
python tools/test_llm_response_validation.py
```

## LLM Decision Logs

When LLM is enabled, every classification decision is logged to:

```
data/logs/llm_decisions.jsonl
```

Each line is a JSON object containing:
- `user_input`, `rule_intent`, `final_intent`
- `llm_intent`, `llm_confidence`, `used_llm`, `accepted`
- `rejected_reason`: `llm_disabled` | `rule_preferred` | `low_confidence` | `invalid_intent` | `backend_failure` | `null`
- `reason`, `timestamp`, `llm_backend`

Full prompts and raw model responses are not logged by default.

Test the logging without running the full shell:
```bash
python tools/test_llm_decision_log.py
```

## Behavioral Scheduler

The shell includes a disabled-by-default passive behavior scheduler. When enabled, it can propose occasional non-mobile expressive actions (chirps, scans, flutter) based on idle time. All scheduled actions still pass through the safety layer.

Enable in `config/body.json`:
```json
"behavior": {
  "enabled": true
}
```

Commands:
```
behavior status    — show scheduler state
behavior tick      — manually trigger a forced tick
```

The scheduler is NOT an autonomous agent. It proposes only pre-configured safe expressive actions. No threading, planning, or LLM involvement.

