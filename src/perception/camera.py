"""
Camera backend — OpenCV webcam capture.

OpenCV is optional. If unavailable the backend marks itself not ready
and all operations fail safely — no crash.

This backend is READ-ONLY:
- single-frame capture only
- no streaming, no preview windows, no continuous loops
- no body actions triggered here

Captures produce structured metadata which is stored on the instance
and optionally appended to a JSONL audit log.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Camera:

    def __init__(self, config: dict) -> None:
        self.config                   = config
        self.device_index: int        = config.get("device_index", 0)
        self.width: int               = config.get("capture_width", 640)
        self.height: int              = config.get("capture_height", 480)
        self.save_captures: bool      = config.get("save_captures", True)
        self.capture_dir              = PROJECT_ROOT / config.get(
                                            "capture_directory", "data/captures")

        diag_cfg                      = config.get("diagnostics", {})
        self.save_metadata: bool      = diag_cfg.get("save_metadata", False)
        raw_log                       = diag_cfg.get("metadata_log",
                                            "data/captures/capture_log.jsonl")
        self.metadata_log             = PROJECT_ROOT / raw_log

        self.ready                            = False
        self.last_capture_path: Optional[str] = None
        self.last_capture_metadata: Optional[dict] = None

        self._cap  = None   # cv2.VideoCapture handle
        self._cv2  = None   # module ref, None if unavailable

        self._init()

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init(self) -> None:
        try:
            import cv2
            self._cv2 = cv2
        except ImportError:
            print("[CAMERA] OpenCV unavailable — install with: pip install opencv-python")
            return

        cap = self._cv2.VideoCapture(self.device_index)
        if not cap.isOpened():
            print(f"[CAMERA] Unable to open camera device {self.device_index}")
            cap.release()
            return

        cap.set(self._cv2.CAP_PROP_FRAME_WIDTH,  self.width)
        cap.set(self._cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap  = cap
        self.ready = True
        print(f"[CAMERA] Ready — device {self.device_index} "
              f"({self.width}×{self.height})")

    # ── Capture ───────────────────────────────────────────────────────────────

    def capture_frame(self) -> Optional[str]:
        """
        Capture a single frame, save as timestamped JPG, return path.
        Records metadata on success and failure.
        """
        ts = datetime.now().isoformat(timespec="seconds")

        if not self.ready or self._cap is None:
            print("[CAMERA] Camera not ready — cannot capture frame.")
            self._record_metadata({
                "timestamp": ts,
                "path": None,
                "device_index": self.device_index,
                "success": False,
                "reason": "camera_not_ready",
            })
            return None

        ret, frame = self._cap.read()
        if not ret or frame is None:
            print("[CAMERA] Failed to capture frame.")
            self._record_metadata({
                "timestamp": ts,
                "path": None,
                "device_index": self.device_index,
                "success": False,
                "reason": "frame_read_failed",
            })
            return None

        actual_h, actual_w = frame.shape[:2]

        if self.save_captures:
            self.capture_dir.mkdir(parents=True, exist_ok=True)
            filename = f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            path     = self.capture_dir / filename

            ok = self._cv2.imwrite(str(path), frame)
            if not ok:
                print(f"[CAMERA] Failed to write capture to {path}")
                self._record_metadata({
                    "timestamp": ts,
                    "path": None,
                    "device_index": self.device_index,
                    "success": False,
                    "reason": "write_failed",
                })
                return None

            path_str = str(path)
            meta = {
                "timestamp":        ts,
                "path":             path_str,
                "device_index":     self.device_index,
                "requested_width":  self.width,
                "requested_height": self.height,
                "actual_width":     actual_w,
                "actual_height":    actual_h,
                "success":          True,
            }
            self.last_capture_path = path_str
            self._record_metadata(meta)
            print(f"[CAMERA] Captured frame:\n  {path_str}")
            return path_str

        # save_captures disabled
        meta = {
            "timestamp":        ts,
            "path":             None,
            "device_index":     self.device_index,
            "requested_width":  self.width,
            "requested_height": self.height,
            "actual_width":     actual_w,
            "actual_height":    actual_h,
            "success":          True,
            "note":             "save_captures disabled",
        }
        self._record_metadata(meta)
        print("[CAMERA] Frame captured (save_captures disabled).")
        return "__in_memory__"

    # ── Metadata log ──────────────────────────────────────────────────────────

    def _record_metadata(self, meta: dict) -> None:
        self.last_capture_metadata = meta
        if not self.save_metadata:
            return
        try:
            self.metadata_log.parent.mkdir(parents=True, exist_ok=True)
            with self.metadata_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(meta) + "\n")
        except OSError as exc:
            print(f"[CAMERA] Failed to write metadata log: {exc}")

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def run_diagnostics(self, probe_indices: list) -> dict:
        """
        Probe a list of device indices. No frames saved, no preview.
        Returns a structured result dict.
        """
        result = {
            "opencv_available":     self._cv2 is not None,
            "configured_device":    self.device_index,
            "probe_indices":        probe_indices,
            "devices":              [],
        }

        if self._cv2 is None:
            return result

        for idx in probe_indices:
            entry: dict = {"index": idx, "opened": False}
            try:
                cap = self._cv2.VideoCapture(idx)
                if cap.isOpened():
                    entry["opened"] = True
                    entry["width"]  = int(cap.get(self._cv2.CAP_PROP_FRAME_WIDTH))
                    entry["height"] = int(cap.get(self._cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
            except Exception as exc:
                entry["error"] = str(exc)
            result["devices"].append(entry)

        return result

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "opencv_available":      self._cv2 is not None,
            "device_index":          self.device_index,
            "ready":                 self.ready,
            "last_capture_path":     self.last_capture_path,
            "last_capture_metadata": self.last_capture_metadata,
        }

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap  = None
            self.ready = False
