"""
Session-scoped perception controller.

Instantiated once at startup alongside RobotState and BodyController.
Owns the camera backend for the full runtime session.
"""

import json
from pathlib import Path
from typing import Optional

PROJECT_ROOT     = Path(__file__).resolve().parents[2]
BODY_CONFIG_PATH = PROJECT_ROOT / "config" / "body.json"

_DEFAULT_CAMERA_CONFIG = {
    "enabled":           False,
    "device_index":      0,
    "capture_width":     640,
    "capture_height":    480,
    "save_captures":     True,
    "capture_directory": "data/captures",
    "diagnostics": {
        "probe_indices":  [0, 1, 2],
        "save_metadata":  False,
        "metadata_log":   "data/captures/capture_log.jsonl",
    },
}


def _load_camera_config() -> dict:
    try:
        cfg = json.loads(BODY_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("camera", _DEFAULT_CAMERA_CONFIG)
    except (FileNotFoundError, json.JSONDecodeError):
        return _DEFAULT_CAMERA_CONFIG


class PerceptionController:

    def __init__(self) -> None:
        cam_cfg        = _load_camera_config()
        self._enabled  = cam_cfg.get("enabled", False)
        self._diag_cfg = cam_cfg.get("diagnostics", {})
        self._camera   = None

        if self._enabled:
            from perception.camera import Camera
            self._camera = Camera(cam_cfg)
            if self._camera.ready:
                print("[PERCEPTION] Camera backend ready.")
            else:
                print("[PERCEPTION] Camera initialized but not ready "
                      "(device unavailable or OpenCV missing).")
        else:
            print("[PERCEPTION] Camera disabled.")

    # ── Capture ───────────────────────────────────────────────────────────────

    def capture_frame(self) -> Optional[str]:
        if not self._enabled:
            print("[PERCEPTION] Camera is disabled in config.")
            return None
        if self._camera is None:
            print("[PERCEPTION] No camera backend available.")
            return None
        return self._camera.capture_frame()

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def run_camera_diagnostics(self) -> dict:
        probe_indices = self._diag_cfg.get("probe_indices", [0, 1, 2])

        print("\n[CAMERA DIAGNOSTICS]")

        if not self._enabled:
            print("  Camera is disabled in config.")
            print("  Set \"camera.enabled\": true to run diagnostics.")
            return {"enabled": False}

        if self._camera is None:
            print("  No camera backend available.")
            return {"enabled": True, "camera_available": False}

        result = self._camera.run_diagnostics(probe_indices)

        print(f"  OpenCV available     : {result['opencv_available']}")
        print(f"  Configured device    : {result['configured_device']}")
        print(f"  Probe indices        : {', '.join(str(i) for i in result['probe_indices'])}")
        print()

        if not result["opencv_available"]:
            print("  OpenCV not available — install with: pip install opencv-python")
            return result

        for dev in result["devices"]:
            idx    = dev["index"]
            opened = dev.get("opened", False)
            if opened:
                w = dev.get("width", "?")
                h = dev.get("height", "?")
                print(f"  index {idx}: opened=True   {w}x{h}")
            elif "error" in dev:
                print(f"  index {idx}: error — {dev['error']}")
            else:
                print(f"  index {idx}: opened=False")

        return result

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        if self._camera is not None:
            cs = self._camera.get_status()
            return {
                "camera_enabled":          self._enabled,
                "camera_ready":            cs["ready"],
                "camera_device_index":     cs["device_index"],
                "last_capture":            cs["last_capture_path"],
                "last_capture_metadata":   cs["last_capture_metadata"],
            }
        return {
            "camera_enabled":          self._enabled,
            "camera_ready":            False,
            "camera_device_index":     None,
            "last_capture":            None,
            "last_capture_metadata":   None,
        }
