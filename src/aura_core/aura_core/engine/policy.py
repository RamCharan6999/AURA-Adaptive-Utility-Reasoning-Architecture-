"""Policy definitions for the AURA demo.

A policy is a *mode of operation* — not where the robot goes, but HOW it
behaves while getting there. Policies are plain data; all scoring lives in
the planner (planners/utility_planner.py) and all explanation logic lives
in AURA (core/explanation_engine.py).

Two calibration fields extend the original spec (see CALIBRATION_NOTES.md):

* ``emergency_only`` — the policy is only eligible for selection when
  mission_priority == 'emergency'. Without this, EMERGENCY_RUSH's raw
  speed makes it win routine deliveries, which is semantically wrong.
* ``emergency_override`` — under an emergency the policy receives an extra
  urgency credit on its time score ("override all constraints"), allowing
  a purpose-built emergency policy to out-score a merely fast one.
* ``localization_replan`` — the policy actively replans when localization
  degrades, so it is immune to the pose-uncertainty safety penalty.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass(frozen=True)
class Policy:
    """A candidate operating mode for the robot."""

    name: str
    description: str
    base_speed: float            # 0.0 - 1.0 fraction of max speed
    power_consumption: float     # 0.0 - 1.0
    safety_tolerance: float      # 0.0 (paranoid) - 1.0 (careful) per spec
    emergency_only: bool = False
    emergency_override: bool = False
    localization_replan: bool = False

    def as_dict(self) -> Dict:
        """Serialise to a plain dict."""
        return asdict(self)


# The five candidate policies from the AURA master context document.
DEFAULT_POLICIES: List[Policy] = [
    Policy(
        name="FAST_DELIVERY",
        description="Maximize speed, minimize delivery time",
        base_speed=0.95,
        power_consumption=0.8,
        safety_tolerance=0.3,
    ),
    Policy(
        name="SAFE_MODE",
        description="Reduce speed, extra caution near humans",
        base_speed=0.60,
        power_consumption=0.4,
        safety_tolerance=0.9,
    ),
    Policy(
        name="ENERGY_SAVE",
        description="Slow cruise, conserve battery",
        base_speed=0.50,
        power_consumption=0.2,
        safety_tolerance=0.7,
    ),
    Policy(
        name="EMERGENCY_RUSH",
        description="Override all constraints, maximum urgency",
        base_speed=1.00,
        power_consumption=1.0,
        safety_tolerance=0.1,
        emergency_only=True,
        emergency_override=True,
    ),
    Policy(
        name="CAUTIOUS_EXPLORE",
        description="Slow + replan when localization drops",
        base_speed=0.30,
        power_consumption=0.3,
        safety_tolerance=0.95,
        localization_replan=True,
    ),
]


def policy_by_name(name: str, policies: List[Policy] = DEFAULT_POLICIES) -> Policy:
    """Look a policy up by name, raising KeyError if unknown."""
    for policy in policies:
        if policy.name == name:
            return policy
    raise KeyError(f"Unknown policy: {name}")
