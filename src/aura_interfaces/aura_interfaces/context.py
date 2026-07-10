"""Context and weight primitives for AURA.

RobotContext mirrors the planned ROS2 RobotContext.msg. It captures the
world state as the robot perceives it. QAWeights mirrors AuraWeights.msg
and captures what the human operator currently cares about.

AURA never mutates these objects; it only reads them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional


# Ordered mapping of mission priority to a numeric level so that a
# categorical change can be quantified for trigger detection.
MISSION_LEVELS: Dict[str, int] = {"normal": 0, "urgent": 1, "emergency": 2}

# Normalisation scale per numeric context variable. Deltas are divided by
# these so a 1 m change in human proximity is comparable to a 0.2 change
# in battery level when deciding which variable changed "most".
CONTEXT_SCALES: Dict[str, float] = {
    "battery_level": 1.0,
    "human_proximity": 5.0,          # metres; 5 m is "far" in the warehouse
    "obstacle_density": 1.0,
    "localization_confidence": 1.0,
    "sensor_health": 1.0,
}

CONTEXT_UNITS: Dict[str, str] = {
    "battery_level": "fraction",
    "human_proximity": "m",
    "obstacle_density": "fraction",
    "localization_confidence": "fraction",
    "sensor_health": "fraction",
    "mission_priority": "level",
}


@dataclass
class RobotContext:
    """Snapshot of the robot's sensed world state (RobotContext.msg)."""

    battery_level: float                 # 0.0 - 1.0
    human_proximity: float               # metres to nearest human
    obstacle_density: float              # 0.0 - 1.0
    localization_confidence: float       # 0.0 - 1.0
    mission_priority: str = "normal"     # normal / urgent / emergency
    sensor_health: float = 1.0           # 0.0 - 1.0 (reserved for Phase 2)
    timestamp: float = 0.0               # simulation time, seconds

    def copy(self) -> "RobotContext":
        """Return an independent copy of this context."""
        return RobotContext(**asdict(self))

    def as_dict(self) -> Dict[str, float]:
        """Serialise to a plain dict (for logging / JSON)."""
        return asdict(self)

    def numeric_fields(self) -> Dict[str, float]:
        """Return only the numeric context variables."""
        return {
            "battery_level": self.battery_level,
            "human_proximity": self.human_proximity,
            "obstacle_density": self.obstacle_density,
            "localization_confidence": self.localization_confidence,
            "sensor_health": self.sensor_health,
        }

    def normalized_deltas(self, previous: "RobotContext") -> Dict[str, float]:
        """Normalised absolute change of every context variable vs `previous`.

        Mission priority is mapped onto MISSION_LEVELS and a one-level jump
        is treated as a delta of 1.0 (a categorical change is always
        significant).
        """
        deltas: Dict[str, float] = {}
        prev = previous.numeric_fields()
        for name, value in self.numeric_fields().items():
            scale = CONTEXT_SCALES.get(name, 1.0)
            deltas[name] = abs(value - prev[name]) / scale
        if self.mission_priority != previous.mission_priority:
            jump = abs(
                MISSION_LEVELS.get(self.mission_priority, 0)
                - MISSION_LEVELS.get(previous.mission_priority, 0)
            )
            deltas["mission_priority"] = float(max(jump, 1))
        else:
            deltas["mission_priority"] = 0.0
        return deltas


@dataclass
class QAWeights:
    """Operator preference weights over quality attributes (AuraWeights.msg).

    Weights must sum to 1.0 (within floating point tolerance).
    """

    w_safety: float
    w_time: float
    w_energy: float

    def __post_init__(self) -> None:
        total = self.w_safety + self.w_time + self.w_energy
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"QA weights must sum to 1.0, got {total:.4f} "
                f"({self.w_safety}, {self.w_time}, {self.w_energy})"
            )

    def as_dict(self) -> Dict[str, float]:
        """Serialise to {'safety': w, 'time': w, 'energy': w}."""
        return {"safety": self.w_safety, "time": self.w_time, "energy": self.w_energy}

    def weight_of(self, qa_name: str) -> float:
        """Look a weight up by quality attribute name."""
        return self.as_dict()[qa_name]

    def changed_from(self, previous: Optional["QAWeights"]) -> bool:
        """True if any weight differs from `previous` beyond tolerance."""
        if previous is None:
            return False
        return any(
            abs(a - b) > 1e-9
            for a, b in zip(
                (self.w_safety, self.w_time, self.w_energy),
                (previous.w_safety, previous.w_time, previous.w_energy),
            )
        )
