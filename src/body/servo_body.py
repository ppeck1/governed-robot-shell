"""
Servo body backend — PCA9685 expression control.

Hardware libraries (adafruit_pca9685, board, busio) are optional.
If unavailable the backend marks itself not ready and all actions
run as dry-run: angles and pulses are printed but nothing moves.

Locomotion actions are refused at this layer regardless of safety state.
This backend handles expression channels only.

Channel angles must stay within the bounds defined in config/body.json.
Channels return to home after each action unless
config["motion"]["return_home_after_action"] is False.
"""

import time
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

# Pulse range for a standard 50 Hz servo on a 12-bit PCA9685.
# These are starting defaults; tune per servo after calibration.
_PULSE_MIN = 150   # ~0°
_PULSE_MAX = 600   # ~180°

_LOCOMOTION_ACTIONS = {"step_forward"}


# ── Pulse math ───────────────────────────────────────────────────────────────

def _angle_to_pulse(angle: float, ch_min: float, ch_max: float) -> int:
    angle = max(ch_min, min(ch_max, angle))
    fraction = (angle - ch_min) / (ch_max - ch_min)
    return int(_PULSE_MIN + fraction * (_PULSE_MAX - _PULSE_MIN))


# ── ServoBody ────────────────────────────────────────────────────────────────

class ServoBody:

    def __init__(self, servo_config: dict, motion_config: Optional[dict] = None):
        self.servo_config  = servo_config
        self.motion_config = motion_config or {}
        self.channels: dict = servo_config.get("channels", {})
        self.step_delay    = self.motion_config.get("step_delay_seconds", 0.25)
        self.return_home   = self.motion_config.get("return_home_after_action", True)
        self.dry_run       = True
        self.driver        = None
        self.positions: dict = {}
        self._init_driver()

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init_driver(self) -> None:
        try:
            import board
            import busio
            from adafruit_pca9685 import PCA9685
        except ImportError as exc:
            print(f"[SERVO BODY] Hardware libraries unavailable: {exc}")
            print("[SERVO BODY] Dry-run mode — angles printed, nothing moves.")
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            pca = PCA9685(i2c)
            pca.frequency = self.servo_config.get("frequency_hz", 50)
            self.driver  = pca
            self.dry_run = False
            print(f"[SERVO BODY] PCA9685 ready at "
                  f"{self.servo_config.get('frequency_hz', 50)} Hz.")
        except Exception as exc:
            print(f"[SERVO BODY] PCA9685 init failed: {exc}")
            print("[SERVO BODY] Dry-run mode.")

    # ── Low-level write ───────────────────────────────────────────────────────

    def _write(self, ch_name: str, angle: float) -> None:
        ch_cfg = self.channels.get(ch_name)
        if ch_cfg is None:
            print(f"[SERVO BODY] Unknown channel '{ch_name}' — skipped.")
            return

        ch_min = ch_cfg["min_angle"]
        ch_max = ch_cfg["max_angle"]
        bounded = max(ch_min, min(ch_max, angle))

        if bounded != angle:
            print(f"[SERVO BODY] {ch_name}: {angle:.1f}° clamped to {bounded:.1f}°")

        pulse  = _angle_to_pulse(bounded, ch_min, ch_max)
        ch_num = ch_cfg["channel"]

        if self.dry_run:
            print(f"[SERVO BODY] DRY  {ch_name:>16}  {bounded:6.1f}°  pulse={pulse}")
        else:
            self.driver.channels[ch_num].duty_cycle = pulse << 4
            print(f"[SERVO BODY] MOVE {ch_name:>16}  {bounded:6.1f}°  pulse={pulse}")

        self.positions[ch_name] = bounded
        time.sleep(self.step_delay)

    def _home(self, ch_name: str) -> None:
        ch_cfg = self.channels.get(ch_name)
        if ch_cfg:
            self._write(ch_name, ch_cfg["home_angle"])

    def _home_all(self) -> None:
        for name in self.channels:
            self._home(name)

    def _maybe_home_all(self) -> None:
        if self.return_home:
            self._home_all()

    # ── Expression actions ────────────────────────────────────────────────────

    def _do_head_turn_left_right(self) -> None:
        ch = self.channels.get("head_yaw", {})
        self._write("head_yaw", ch.get("min_angle", 70))
        self._write("head_yaw", ch.get("max_angle", 110))
        self._home("head_yaw")

    def _do_idle_flutter(self) -> None:
        for name in ("left_flutter", "right_flutter"):
            ch = self.channels.get(name, {})
            home = ch.get("home_angle", 90)
            self._write(name, home - 5)
            self._write(name, home + 5)
            self._home(name)

    def _do_express_curious(self) -> None:
        ch = self.channels.get("head_yaw", {})
        home   = ch.get("home_angle", 90)
        ch_max = ch.get("max_angle", 120)
        tilt   = min(home + 15, ch_max)
        self._write("head_yaw", tilt)
        self._do_idle_flutter()
        self._home("head_yaw")

    def _do_express_confused(self) -> None:
        lf = self.channels.get("left_flutter",  {})
        rf = self.channels.get("right_flutter", {})
        self._write("left_flutter",  lf.get("home_angle", 90) - 8)
        self._write("right_flutter", rf.get("home_angle", 90) + 8)
        self._write("left_flutter",  lf.get("home_angle", 90) + 8)
        self._write("right_flutter", rf.get("home_angle", 90) - 8)
        self._home("left_flutter")
        self._home("right_flutter")

    def _do_wake(self) -> None:
        print("[SERVO BODY] Waking — bringing all channels to home.")
        self._home_all()

    def _do_sleep(self) -> None:
        print("[SERVO BODY] Sleeping — lowering flutter servos.")
        for name in ("left_flutter", "right_flutter"):
            ch = self.channels.get(name, {})
            self._write(name, ch.get("min_angle", 75))

    def _do_enter_idle_mode(self) -> None:
        print("[SERVO BODY] Entering idle mode — all channels to home.")
        self._home_all()

    def _do_play_chirp(self) -> None:
        print("[SERVO BODY] Chirp requested — no audio backend yet.")

    # ── Public interface ──────────────────────────────────────────────────────

    def execute_action(self, action: str) -> None:
        if action in _LOCOMOTION_ACTIONS:
            print(f"[SERVO BODY] Locomotion action '{action}' refused by servo backend.")
            return

        dispatch = {
            "head_turn_left_right": self._do_head_turn_left_right,
            "idle_flutter":          self._do_idle_flutter,
            "express_curious":       self._do_express_curious,
            "express_confused":      self._do_express_confused,
            "wake":                  self._do_wake,
            "sleep":                 self._do_sleep,
            "enter_idle_mode":       self._do_enter_idle_mode,
            "play_chirp":            self._do_play_chirp,
        }

        handler = dispatch.get(action)
        if handler:
            handler()
            self._maybe_home_all()
        else:
            print(f"[SERVO BODY] Unknown action '{action}' — no movement.")


    def get_positions(self) -> dict:
        """Return a snapshot of current tracked channel positions."""
        return dict(self.positions)


# ── Standalone bounded write helper (used by calibrate_servo.py) ─────────────

def move_named_servo(name: str, angle: float,
                     config: Optional[dict] = None) -> bool:
    """
    Validate and report a bounded angle for a named channel.
    Used by calibration tools that manage their own driver.
    Returns True if accepted, False if out of bounds or unknown.
    """
    if config is None:
        print("[SERVO BODY] move_named_servo: no config provided.")
        return False

    channels = config.get("channels", {})
    ch_cfg   = channels.get(name)
    if ch_cfg is None:
        print(f"[SERVO BODY] move_named_servo: unknown channel '{name}'.")
        return False

    ch_min = ch_cfg["min_angle"]
    ch_max = ch_cfg["max_angle"]

    if angle < ch_min or angle > ch_max:
        print(f"[SERVO BODY] move_named_servo: {angle:.1f}° refused — "
              f"outside bounds [{ch_min}°–{ch_max}°] for '{name}'.")
        return False

    pulse = _angle_to_pulse(angle, ch_min, ch_max)
    print(f"[SERVO BODY] {name}  requested={angle:.1f}°  bounded={angle:.1f}°  "
          f"pulse={pulse}")
    return True
