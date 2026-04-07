"""
Bastion: Cybersecurity Incident Response — Core Environment

Extends openenv Environment for full spec compliance.
"""

from __future__ import annotations

import random
from typing import Any, Optional
from uuid import uuid4

from openenv.core.env_server import Environment

from models import (
    IncidentAction,
    IncidentObservation,
    IncidentState,
    ActionType,
    ACTION_NAMES,
    NUM_ACTIONS,
    make_observation,
)
from dynamics import step_dynamics
from reward import (
    compute_step_reward,
    compute_penalties,
    compute_task_weighted_score,
    compute_baseline_comparison,
)
from baseline import run_baseline
from tasks import get_task, TaskConfig


class BastionEnvironment(Environment[IncidentAction, IncidentObservation, IncidentState]):
    """
    OpenEnv-compatible RL environment for cybersecurity incident response.

    The agent is an Incident Commander responding to a live cyberattack.
    12 time steps (hours), 10 possible actions, 8 network systems.
    """

    def __init__(self) -> None:
        super().__init__()
        self._task: Optional[TaskConfig] = None
        self._state: IncidentState = IncidentState()
        self._rng: random.Random = random.Random(42)
        self._action_history: list[tuple[int, int]] = []
        self._cumulative_reward: float = 0.0
        self._baseline_state: Optional[IncidentState] = None
        self._done: bool = False
        self._initialized: bool = False
        self._alerts_accurate: bool = False

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> IncidentObservation:
        task_id = kwargs.get("task_id", "easy_1")

        self._task = get_task(task_id)
        self._state = self._task.initial_state.clone()
        self._state.episode_id = episode_id or str(uuid4())
        self._state.step_count = 0
        self._state.task_id = task_id

        effective_seed = seed if seed is not None else self._task.seed
        self._rng = random.Random(effective_seed)

        self._action_history = []
        self._cumulative_reward = 0.0
        self._done = False
        self._initialized = True
        self._alerts_accurate = False

        # Pre-compute baseline
        self._baseline_state = run_baseline(task_id, policy_name="naive")

        return make_observation(
            self._state,
            self._rng,
            task_description=self._task.description,
            done=False,
            reward=None,
            alerts_accurate=False,
        )

    def step(
        self,
        action: IncidentAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> IncidentObservation:
        if not self._initialized:
            self.reset(task_id="easy_1")
        if self._done:
            self.reset(task_id=self._state.task_id)

        action_idx = action.action
        target_idx = action.target_system

        # Snapshot for reward
        prev_state = self._state.clone()

        # Execute transition
        stamina_cost, alerts_accurate = step_dynamics(
            self._state, action_idx, target_idx, self._rng
        )
        self._alerts_accurate = alerts_accurate
        self._action_history.append((action_idx, target_idx))

        # Compute reward
        step_reward = compute_step_reward(prev_state, self._state, stamina_cost)
        penalty = compute_penalties(self._state)
        total_reward = step_reward + penalty
        self._cumulative_reward += total_reward

        # Check termination
        done = False
        info: dict[str, Any] = {
            "hour": self._state.hour,
            "action_name": ACTION_NAMES.get(action_idx, str(action_idx)),
            "target_system": self._state.systems[target_idx].name if target_idx < len(self._state.systems) else str(target_idx),
            "stamina_cost": round(stamina_cost, 3),
            "step_reward": round(step_reward, 6),
            "penalty": round(penalty, 6),
        }

        if self._state.data_exfiltrated >= 1.0:
            done = True
            info["termination_reason"] = "total_data_breach"
        elif self._state.hour >= self._task.max_hours:
            done = True
            info["termination_reason"] = "time_expired"

        if done:
            self._done = True
            agent_score = compute_task_weighted_score(
                self._state, self._task.scoring_weights
            )
            baseline_score = compute_task_weighted_score(
                self._baseline_state, self._task.scoring_weights
            )
            comparison = compute_baseline_comparison(
                self._state, self._baseline_state, self._task.scoring_weights
            )
            info["agent_final_score"] = round(agent_score, 6)
            info["baseline_final_score"] = round(baseline_score, 6)
            info["comparison_score"] = round(comparison, 6)
            info["cumulative_reward"] = round(self._cumulative_reward, 6)
            info["data_exfiltrated"] = round(self._state.data_exfiltrated, 4)
            info["attacker_progress"] = round(self._state.attacker_progress, 4)
            info["final_state"] = self._state.snapshot()

        obs = make_observation(
            self._state,
            self._rng,
            task_description=self._task.description if not done else "",
            done=done,
            reward=total_reward,
            alerts_accurate=alerts_accurate,
        )
        obs.metadata = info

        return obs

    @property
    def state(self) -> IncidentState:
        return self._state
