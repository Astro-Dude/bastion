"""
Bastion: Cybersecurity Incident Response Environment — Data Models

All models extend OpenEnv base types (Action, Observation, State).
"""

from __future__ import annotations

import random
from enum import IntEnum
from typing import Any, Dict, List, Optional

from pydantic import Field

from openenv.core.env_server import Action, Observation, State


# ---------------------------------------------------------------------------
# Systems in the network
# ---------------------------------------------------------------------------

SYSTEM_NAMES = [
    "web_server",
    "app_server",
    "database",
    "file_server",
    "email_server",
    "workstations",
    "backup_server",
    "firewall",
]
NUM_SYSTEMS = len(SYSTEM_NAMES)

# Which systems can the attacker reach from each system (adjacency)
NETWORK_ADJACENCY: Dict[str, List[str]] = {
    "web_server": ["app_server", "firewall"],
    "app_server": ["web_server", "database", "file_server"],
    "database": ["app_server", "backup_server"],
    "file_server": ["app_server", "email_server", "workstations"],
    "email_server": ["file_server", "workstations"],
    "workstations": ["file_server", "email_server", "app_server"],
    "backup_server": ["database"],
    "firewall": ["web_server"],
}

# How important is each system (affects scoring)
SYSTEM_CRITICALITY: Dict[str, float] = {
    "web_server": 0.6,
    "app_server": 0.8,
    "database": 1.0,
    "file_server": 0.7,
    "email_server": 0.4,
    "workstations": 0.3,
    "backup_server": 0.9,
    "firewall": 0.5,
}

# Systems that hold exfiltrable data
DATA_SYSTEMS = {"database", "file_server", "email_server", "backup_server"}

# Systems that are production-critical services
SERVICE_SYSTEMS = {"web_server", "app_server", "database", "email_server"}


# ---------------------------------------------------------------------------
# Alert model
# ---------------------------------------------------------------------------

class AlertSeverity(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


# ---------------------------------------------------------------------------
# Action Space
# ---------------------------------------------------------------------------

class ActionType(IntEnum):
    INVESTIGATE_SYSTEM = 0
    ISOLATE_SYSTEM = 1
    PATCH_VULNERABILITY = 2
    RESTORE_FROM_BACKUP = 3
    ANALYZE_ALERTS = 4
    DEPLOY_MONITORING = 5
    ESCALATE_TO_MANAGEMENT = 6
    BLOCK_EXTERNAL_TRAFFIC = 7
    HUNT_THREAT = 8
    COORDINATE_TEAM = 9


ACTION_NAMES: Dict[int, str] = {int(a): a.name.lower() for a in ActionType}
NUM_ACTIONS = len(ActionType)

# Actions that target a specific system need a target
TARGETED_ACTIONS = {
    ActionType.INVESTIGATE_SYSTEM,
    ActionType.ISOLATE_SYSTEM,
    ActionType.PATCH_VULNERABILITY,
    ActionType.RESTORE_FROM_BACKUP,
    ActionType.HUNT_THREAT,
}


class IncidentAction(Action):
    """Agent picks an action and optionally a target system."""
    action: int = Field(
        ..., ge=0, lt=NUM_ACTIONS,
        description="Action index (0-9). See ActionType enum.",
    )
    target_system: int = Field(
        default=0, ge=0, lt=NUM_SYSTEMS,
        description="Target system index (0-7) for targeted actions. "
                    "0=web_server, 1=app_server, 2=database, 3=file_server, "
                    "4=email_server, 5=workstations, 6=backup_server, 7=firewall",
    )


# ---------------------------------------------------------------------------
# Per-system state
# ---------------------------------------------------------------------------

class SystemState(State):
    """State of a single system in the network."""
    name: str = ""
    compromised: bool = False
    isolated: bool = False
    investigated: bool = False
    has_backdoor: bool = False
    integrity: float = Field(default=1.0, ge=0.0, le=1.0)
    criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    monitoring_level: int = Field(default=0, ge=0, le=3)  # 0=none, 3=full
    patched: bool = False


# ---------------------------------------------------------------------------
# Alert (what the agent sees in the queue)
# ---------------------------------------------------------------------------

class Alert(State):
    """A security alert — may be real or false positive."""
    source_system: str = ""
    severity: int = 0
    message: str = ""
    is_true_positive: bool = True  # hidden from agent in observation
    hour: int = 0


# ---------------------------------------------------------------------------
# Full incident state (ground truth)
# ---------------------------------------------------------------------------

class IncidentState(State):
    """Full ground-truth state of the incident response simulation."""
    systems: List[SystemState] = Field(default_factory=list)
    alerts: List[Alert] = Field(default_factory=list)

    # Global metrics
    attacker_progress: float = Field(default=0.0, ge=0.0, le=1.0)
    attacker_stealth: float = Field(default=0.8, ge=0.0, le=1.0)
    data_exfiltrated: float = Field(default=0.0, ge=0.0, le=1.0)
    services_disrupted: int = Field(default=0, ge=0)
    team_stamina: float = Field(default=1.0, ge=0.0, le=1.0)
    hour: int = Field(default=0, ge=0)

    # Tracking
    external_blocked: bool = False
    management_escalated: bool = False
    management_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    task_id: str = ""

    def get_system(self, name: str) -> SystemState:
        for s in self.systems:
            if s.name == name:
                return s
        raise ValueError(f"Unknown system: {name}")

    def get_system_by_idx(self, idx: int) -> SystemState:
        return self.systems[idx]

    @property
    def compromised_count(self) -> int:
        return sum(1 for s in self.systems if s.compromised and not s.isolated)

    @property
    def isolated_count(self) -> int:
        return sum(1 for s in self.systems if s.isolated)

    @property
    def investigated_count(self) -> int:
        return sum(1 for s in self.systems if s.investigated)

    @property
    def services_intact(self) -> int:
        return sum(
            1 for s in self.systems
            if s.name in SERVICE_SYSTEMS and not s.isolated and s.integrity > 0.3
        )

    def snapshot(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["compromised_count"] = self.compromised_count
        d["isolated_count"] = self.isolated_count
        d["investigated_count"] = self.investigated_count
        d["services_intact"] = self.services_intact
        return d

    def clone(self) -> IncidentState:
        return IncidentState(**self.model_dump())


# ---------------------------------------------------------------------------
# Observation (partial observability)
# ---------------------------------------------------------------------------

class IncidentObservation(Observation):
    """
    What the IR commander sees — noisy, incomplete, delayed.

    Key partial observability:
    - compromise status is UNKNOWN unless system has been investigated
    - data_exfiltrated is estimated with noise
    - alert queue contains false positives
    - attacker_progress is invisible
    """
    # Per-system visible state
    systems_visible: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Visible state of each system (compromise unknown unless investigated)",
    )
    # Alert queue (includes false positives — agent doesn't know which)
    alert_queue: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Recent security alerts (may include false positives)",
    )
    # Global estimates (noisy)
    estimated_breach_severity: str = Field(
        default="unknown",
        description="Estimated severity: unknown, low, medium, high, critical",
    )
    estimated_data_at_risk: float = Field(
        default=0.0,
        description="Estimated fraction of data at risk (noisy, 0-1)",
    )
    services_disrupted: int = Field(default=0)
    services_total: int = Field(default=len(SERVICE_SYSTEMS))
    team_stamina: float = Field(default=1.0)
    hour: int = Field(default=0)
    hours_remaining: int = Field(default=12)
    external_blocked: bool = Field(default=False)
    management_escalated: bool = Field(default=False)
    task_description: str = Field(default="")


def make_observation(
    state: IncidentState,
    rng: random.Random,
    task_description: str = "",
    done: bool = False,
    reward: float | None = None,
    alerts_accurate: bool = False,
) -> IncidentObservation:
    """Build a partially-observable view of the true state."""

    # Per-system: only show compromise if investigated
    systems_vis = []
    for s in state.systems:
        vis: Dict[str, Any] = {
            "name": s.name,
            "isolated": s.isolated,
            "investigated": s.investigated,
            "integrity": round(s.integrity, 2),
            "criticality": s.criticality,
            "monitoring_level": s.monitoring_level,
            "patched": s.patched,
        }
        if s.investigated:
            vis["compromised"] = s.compromised
            vis["has_backdoor"] = s.has_backdoor
        else:
            # Unknown — agent must investigate to find out
            vis["compromised"] = "unknown"
            vis["has_backdoor"] = "unknown"
        systems_vis.append(vis)

    # Alerts: show all but hide is_true_positive unless alerts_accurate
    alert_vis = []
    for a in state.alerts[-6:]:  # show last 6 alerts
        av: Dict[str, Any] = {
            "source_system": a.source_system,
            "severity": ["low", "medium", "high", "critical"][a.severity],
            "message": a.message,
            "hour": a.hour,
        }
        if alerts_accurate:
            av["confirmed"] = a.is_true_positive
        alert_vis.append(av)

    # Estimate breach severity based on what's visible
    investigated = [s for s in state.systems if s.investigated]
    known_compromised = sum(1 for s in investigated if s.compromised)
    if not investigated:
        severity_est = "unknown"
    elif known_compromised == 0:
        severity_est = "low"
    elif known_compromised <= 2:
        severity_est = "medium"
    elif known_compromised <= 4:
        severity_est = "high"
    else:
        severity_est = "critical"

    # Noisy data exfiltration estimate
    noise = rng.gauss(0, 0.1)
    data_est = max(0.0, min(1.0, state.data_exfiltrated + noise))

    # Count disrupted services
    disrupted = sum(
        1 for s in state.systems
        if s.name in SERVICE_SYSTEMS and (s.isolated or s.integrity < 0.3)
    )

    return IncidentObservation(
        systems_visible=systems_vis,
        alert_queue=alert_vis,
        estimated_breach_severity=severity_est,
        estimated_data_at_risk=round(data_est, 3),
        services_disrupted=disrupted,
        team_stamina=round(state.team_stamina, 2),
        hour=state.hour,
        hours_remaining=12 - state.hour,
        external_blocked=state.external_blocked,
        management_escalated=state.management_escalated,
        task_description=task_description,
        done=done,
        reward=reward,
    )
