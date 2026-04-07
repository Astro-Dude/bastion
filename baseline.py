"""
Bastion: Cybersecurity Incident Response — Baseline Policies

Two baseline policies for comparison:
  - no_op: always coordinate_team (cheapest, does nothing useful)
  - naive: fixed rotation (investigate → isolate → patch → repeat)
"""

from __future__ import annotations

import random
from typing import Callable, Tuple

from models import ActionType, IncidentState, SYSTEM_NAMES
from dynamics import step_dynamics
from tasks import get_task


def no_op_policy(state: IncidentState, hour: int) -> Tuple[int, int]:
    """Always coordinate team — cheapest action, no real impact."""
    return (ActionType.COORDINATE_TEAM, 0)


def naive_policy(state: IncidentState, hour: int) -> Tuple[int, int]:
    """
    Rotate through: investigate → isolate → deploy_monitoring → patch
    Targets systems in order (0, 1, 2, ...).
    """
    rotation = [
        ActionType.INVESTIGATE_SYSTEM,
        ActionType.ISOLATE_SYSTEM,
        ActionType.DEPLOY_MONITORING,
        ActionType.PATCH_VULNERABILITY,
    ]
    action = rotation[hour % len(rotation)]
    target = hour % len(SYSTEM_NAMES)
    return (action, target)


BASELINE_POLICIES = {
    "no_op": no_op_policy,
    "naive": naive_policy,
}


def run_baseline(task_id: str, policy_name: str = "naive") -> IncidentState:
    """Run a full episode with the baseline policy. Returns final state."""
    task = get_task(task_id)
    state = task.initial_state.clone()
    rng = random.Random(task.seed)
    policy = BASELINE_POLICIES[policy_name]

    for hour in range(task.max_hours):
        action, target = policy(state, hour)
        step_dynamics(state, action, target, rng)

        # Check catastrophic failure
        if state.data_exfiltrated >= 1.0:
            break

    return state
