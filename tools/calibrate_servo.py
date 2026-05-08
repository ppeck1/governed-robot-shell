"""
Servo calibration utility — Phase 3B.

Isolated from normal robot behavior. Does not use the planner, intent
parser, safety layer, or body_controller. This script exists only to
safely discover real pulse limits for one servo channel.

REQUIRES in config/body.json:
    "calibration": { "enabled": true }

Will refuse to run otherwise. Will fail safely if hardware libraries
are unavailable.

Usage:
    python tools/calibrate_servo.py

Commands during session:
    left     — step current angle left (decrease)
    right    — step current angle right (increase)
    home     — return to start_angle
    status   — print current angle and config
    quit     — exit cleanly
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH  = PROJECT_ROOT / "config" / "body.json"


# ── Config loading ──────────────────────────────────────────────────────────

def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"[CALIBRATION] Config not found: {CONFIG_PATH}")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[CALIBRATION] Config parse error: {exc}")
        sys.exit(1)


def check_enabled(cfg: dict) -> None:
    cal = cfg.get("calibration", {})
    if not cal.get("enabled", False):
        print("[CALIBRATION] Calibration is disabled in config/body.json.")
        print("              Set  \"calibration\": { \"enabled\": true }  to proceed.")
        print("              Do not enable on hardware until servo is physically safe to move.")
        sys.exit(0)


# ── Hardware init ───────────────────────────────────────────────────────────

_PULSE_MIN = 150
_PULSE_MAX = 600


def angle_to_pulse(angle: float, ch_min: float, ch_max: float) -> int:
    angle = max(ch_min, min(ch_max, angle))
    fraction = (angle - ch_min) / (ch_max - ch_min)
    return int(_PULSE_MIN + fraction * (_PULSE_MAX - _PULSE_MIN))


def init_driver(freq_hz: int = 50):
    """Return (pca_driver, True) or (None, False) if libs unavailable."""
    try:
        import board
        import busio
        from adafruit_pca9685 import PCA9685
    except ImportError as exc:
        print(f"[CALIBRATION] Hardware libraries unavailable: {exc}")
        print("[CALIBRATION] Running in DRY-RUN mode — no physical movement.")
        return None, False

    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        pca = PCA9685(i2c)
        pca.frequency = freq_hz
        print(f"[CALIBRATION] PCA9685 initialized at {freq_hz} Hz.")
        return pca, True
    except Exception as exc:
        print(f"[CALIBRATION] PCA9685 init failed: {exc}")
        print("[CALIBRATION] Running in DRY-RUN mode.")
        return None, False


# ── Servo write ─────────────────────────────────────────────────────────────

def write_servo(driver, ch_num: int, angle: float,
                ch_min: float, ch_max: float,
                cal_min: float, cal_max: float,
                dry_run: bool) -> bool:
    """
    Write angle to channel. Returns False and refuses if outside calibration
    bounds. Clamps only to channel hardware limits, not silently.
    """
    if angle < cal_min or angle > cal_max:
        print(f"[CALIBRATION] REFUSED: {angle:.1f}° is outside calibration "
              f"test range [{cal_min}°–{cal_max}°].")
        return False

    pulse = angle_to_pulse(angle, ch_min, ch_max)

    if dry_run:
        print(f"[CALIBRATION] DRY-RUN  angle={angle:.1f}°  pulse={pulse}  "
              f"channel={ch_num}")
    else:
        driver.channels[ch_num].duty_cycle = pulse << 4
        print(f"[CALIBRATION] MOVED    angle={angle:.1f}°  pulse={pulse}  "
              f"channel={ch_num}")

    return True


# ── Session ──────────────────────────────────────────────────────────────────

def run_session(cfg: dict) -> None:
    cal  = cfg["calibration"]
    servo_cfg = cfg.get("servo", {})
    freq = servo_cfg.get("frequency_hz", 50)

    channel_name = cal.get("test_channel", "head_yaw")
    channels     = servo_cfg.get("channels", {})
    ch_cfg       = channels.get(channel_name)

    if ch_cfg is None:
        print(f"[CALIBRATION] Channel '{channel_name}' not found in servo config.")
        sys.exit(1)

    ch_num  = ch_cfg["channel"]
    ch_min  = ch_cfg["min_angle"]
    ch_max  = ch_cfg["max_angle"]
    home    = cal.get("start_angle", ch_cfg.get("home_angle", 90))
    step    = cal.get("step_degrees", 5)
    cal_min = cal.get("min_test_angle", ch_min)
    cal_max = cal.get("max_test_angle", ch_max)

    driver, live = init_driver(freq)
    dry_run = not live
    current = float(home)

    print()
    print("=" * 52)
    print("  SERVO CALIBRATION MODE")
    print(f"  Channel : {channel_name}  (PCA9685 ch {ch_num})")
    print(f"  Test range : {cal_min}° – {cal_max}°")
    print(f"  Step    : {step}°")
    print(f"  Home    : {home}°")
    print(f"  Live hw : {'YES — SERVO WILL MOVE' if live else 'NO — dry-run only'}")
    print("=" * 52)
    print("  Commands: left  right  home  status  quit")
    print("=" * 52)
    print()

    # Move to home at session start
    write_servo(driver, ch_num, current, ch_min, ch_max,
                cal_min, cal_max, dry_run)

    while True:
        try:
            raw = input("cal> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[CALIBRATION] Interrupted.")
            break

        if not raw:
            continue

        if raw == "quit":
            print("[CALIBRATION] Returning to home before exit.")
            write_servo(driver, ch_num, home, ch_min, ch_max,
                        cal_min, cal_max, dry_run)
            print("[CALIBRATION] Session ended.")
            break

        elif raw == "home":
            current = float(home)
            write_servo(driver, ch_num, current, ch_min, ch_max,
                        cal_min, cal_max, dry_run)

        elif raw == "left":
            target = current - step
            if write_servo(driver, ch_num, target, ch_min, ch_max,
                           cal_min, cal_max, dry_run):
                current = target

        elif raw == "right":
            target = current + step
            if write_servo(driver, ch_num, target, ch_min, ch_max,
                           cal_min, cal_max, dry_run):
                current = target

        elif raw == "status":
            print(f"[CALIBRATION] channel={channel_name}  current={current:.1f}°  "
                  f"test_range=[{cal_min}°–{cal_max}°]  "
                  f"hw_bounds=[{ch_min}°–{ch_max}°]  "
                  f"live={'yes' if live else 'dry-run'}")

        else:
            print(f"[CALIBRATION] Unknown command: '{raw}'")
            print("              Valid: left  right  home  status  quit")


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cfg = load_config()
    check_enabled(cfg)
    run_session(cfg)
