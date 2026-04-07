"""
Bastion: Cybersecurity Incident Response — OpenEnv Client
"""

from __future__ import annotations

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.env_client import StepResult

from models import IncidentAction, IncidentObservation, IncidentState


class BastionEnv(EnvClient[IncidentAction, IncidentObservation, IncidentState]):
    """Async OpenEnv client for the Bastion environment."""

    def _step_payload(self, action: IncidentAction) -> Dict[str, Any]:
        return action.model_dump()

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[IncidentObservation]:
        obs_data = payload.get("observation", payload)
        obs = IncidentObservation(**obs_data)
        return StepResult(
            observation=obs,
            reward=payload.get("reward"),
            done=payload.get("done", obs.done),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> IncidentState:
        return IncidentState(**payload)
