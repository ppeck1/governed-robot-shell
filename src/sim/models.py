from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, radians, sin, sqrt
from typing import Any


@dataclass
class SimWorld:
    width: float = 8.0
    depth: float = 8.0
    obstacles: list[dict[str, float | str]] = field(
        default_factory=lambda: [
            {"id": "block-a", "x": 1.6, "z": -1.2, "radius": 0.45},
            {"id": "block-b", "x": -2.2, "z": 1.7, "radius": 0.6},
        ]
    )
    light_sources: list[dict[str, float | str]] = field(
        default_factory=lambda: [{"id": "lamp", "x": 2.5, "z": 2.5, "intensity": 0.8}]
    )
    sound_sources: list[dict[str, float | str]] = field(
        default_factory=lambda: [{"id": "beacon", "x": -2.5, "z": -2.0, "intensity": 0.4}]
    )

    def snapshot(self) -> dict[str, Any]:
        return {
            "width": self.width,
            "depth": self.depth,
            "obstacles": [dict(item) for item in self.obstacles],
            "light_sources": [dict(item) for item in self.light_sources],
            "sound_sources": [dict(item) for item in self.sound_sources],
        }


@dataclass
class SimRobot:
    x: float = 0.0
    z: float = 0.0
    heading_degrees: float = 0.0
    head_yaw_degrees: float = 0.0
    left_flutter_degrees: float = 0.0
    right_flutter_degrees: float = 0.0
    power_state: str = "awake"
    audio_state: str = "idle"
    latest_audio_cue: str | None = None
    cue_count: int = 0
    expression: str = "neutral"
    action_count: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "pose": {
                "x": round(self.x, 3),
                "z": round(self.z, 3),
                "heading_degrees": round(self.heading_degrees, 1),
            },
            "expression": self.expression,
            "power_state": self.power_state,
            "audio_state": self.audio_state,
            "latest_audio_cue": self.latest_audio_cue,
            "cue_count": self.cue_count,
            "channels": {
                "head_yaw": round(self.head_yaw_degrees, 1),
                "left_flutter": round(self.left_flutter_degrees, 1),
                "right_flutter": round(self.right_flutter_degrees, 1),
            },
            "action_count": self.action_count,
        }


@dataclass
class SimObservation:
    nearest_obstacle_distance: float | None
    front_clearance: float
    bump_left: bool
    bump_right: bool
    light_level: float
    sound_level: float

    def snapshot(self) -> dict[str, Any]:
        return {
            "nearest_obstacle_distance": (
                round(self.nearest_obstacle_distance, 3)
                if self.nearest_obstacle_distance is not None
                else None
            ),
            "front_clearance": round(self.front_clearance, 3),
            "bump_left": self.bump_left,
            "bump_right": self.bump_right,
            "light_level": round(self.light_level, 3),
            "sound_level": round(self.sound_level, 3),
        }


def distance(ax: float, az: float, bx: float, bz: float) -> float:
    return sqrt((ax - bx) ** 2 + (az - bz) ** 2)


def build_observation(world: SimWorld, robot: SimRobot) -> SimObservation:
    nearest = None
    front_clearance = min(world.width, world.depth)
    heading = radians(robot.heading_degrees)
    forward_x = sin(heading)
    forward_z = -cos(heading)

    for obstacle in world.obstacles:
        ox = float(obstacle["x"])
        oz = float(obstacle["z"])
        radius = float(obstacle.get("radius", 0.4))
        center_distance = distance(robot.x, robot.z, ox, oz)
        edge_distance = max(0.0, center_distance - radius)
        nearest = edge_distance if nearest is None else min(nearest, edge_distance)

        rel_x = ox - robot.x
        rel_z = oz - robot.z
        forward_distance = rel_x * forward_x + rel_z * forward_z
        lateral_distance = abs(rel_x * forward_z - rel_z * forward_x)
        if forward_distance >= 0 and lateral_distance <= radius + 0.35:
            front_clearance = min(front_clearance, max(0.0, forward_distance - radius))

    light_level = _source_level(world.light_sources, robot)
    sound_level = _source_level(world.sound_sources, robot)
    bump = front_clearance < 0.15
    return SimObservation(
        nearest_obstacle_distance=nearest,
        front_clearance=front_clearance,
        bump_left=bump and robot.head_yaw_degrees < 0,
        bump_right=bump and robot.head_yaw_degrees >= 0,
        light_level=light_level,
        sound_level=sound_level,
    )


def _source_level(sources: list[dict[str, float | str]], robot: SimRobot) -> float:
    level = 0.0
    for source in sources:
        source_distance = max(0.1, distance(robot.x, robot.z, float(source["x"]), float(source["z"])))
        level += float(source.get("intensity", 0.0)) / (source_distance * source_distance)
    return min(1.0, level)
