"""
Bastion: Cybersecurity Incident Response — Task Definitions

Three scenarios of increasing difficulty:
  Easy:   Script kiddie — slow, noisy attacker
  Medium: Ransomware outbreak — fast-spreading, multiple systems
  Hard:   APT actor — stealthy, sophisticated, minimal alerts
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator

from models import (
    AlertSeverity,
    Alert,
    IncidentState,
    SystemState,
    SYSTEM_NAMES,
    SYSTEM_CRITICALITY,
)


class TaskConfig(BaseModel):
    task_id: str
    description: str
    initial_state: IncidentState
    scoring_weights: Dict[str, float]
    max_hours: int = 12
    seed: int = 0

    @model_validator(mode="after")
    def _derive_seed(self) -> "TaskConfig":
        h = hashlib.sha256(self.task_id.encode()).hexdigest()
        self.seed = int(h[:8], 16)
        return self


def _make_systems(compromised: List[str], monitoring: Dict[str, int] | None = None) -> List[SystemState]:
    """Create initial system states."""
    mon = monitoring or {}
    systems = []
    for name in SYSTEM_NAMES:
        systems.append(SystemState(
            name=name,
            compromised=name in compromised,
            isolated=False,
            investigated=False,
            has_backdoor=False,
            integrity=1.0,
            criticality=SYSTEM_CRITICALITY[name],
            monitoring_level=mon.get(name, 0),
            patched=False,
        ))
    return systems


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------

TASKS: Dict[str, TaskConfig] = {}


def _register(cfg: TaskConfig) -> None:
    TASKS[cfg.task_id] = cfg


# --- EASY: Script Kiddie ---
_register(TaskConfig(
    task_id="easy_1",
    description=(
        "SCENARIO: Script Kiddie Attack\n"
        "A low-skill attacker has compromised your web server and is attempting "
        "to move laterally. Their tools are noisy — you're getting clear alerts. "
        "The attacker is slow but persistent. Contain the breach, investigate "
        "affected systems, and minimize data loss.\n"
        "INTEL: Attacker entry point is the web_server. Low stealth capability."
    ),
    initial_state=IncidentState(
        systems=_make_systems(
            compromised=["web_server"],
            monitoring={"web_server": 1, "firewall": 1},
        ),
        alerts=[
            Alert(
                source_system="web_server",
                severity=AlertSeverity.HIGH,
                message="Unauthorized shell access detected on web_server",
                is_true_positive=True,
                hour=0,
            ),
            Alert(
                source_system="firewall",
                severity=AlertSeverity.MEDIUM,
                message="Unusual outbound connection from web_server to unknown IP",
                is_true_positive=True,
                hour=0,
            ),
        ],
        attacker_progress=0.05,
        attacker_stealth=0.4,  # noisy attacker
        data_exfiltrated=0.0,
        services_disrupted=0,
        team_stamina=1.0,
        hour=0,
        external_blocked=False,
        management_escalated=False,
    ),
    scoring_weights={
        "data_protection": 0.30,
        "containment": 0.30,
        "business_continuity": 0.15,
        "forensic": 0.15,
        "sustainability": 0.10,
    },
))


# --- MEDIUM: Ransomware Outbreak ---
_register(TaskConfig(
    task_id="medium_1",
    description=(
        "SCENARIO: Ransomware Outbreak\n"
        "Fast-spreading ransomware has hit your network. The file_server, "
        "workstations, and email_server are already compromised and the malware "
        "is encrypting data rapidly. Multiple alerts are firing — some are real, "
        "some are noise from panicked automated scanners. You must stop the spread, "
        "protect the database and backups, and keep critical services running.\n"
        "INTEL: Ransomware entered via email_server phishing. Spreading fast."
    ),
    initial_state=IncidentState(
        systems=_make_systems(
            compromised=["file_server", "workstations", "email_server"],
            monitoring={"database": 1},
        ),
        alerts=[
            Alert(
                source_system="file_server",
                severity=AlertSeverity.CRITICAL,
                message="Mass file encryption detected on file_server",
                is_true_positive=True,
                hour=0,
            ),
            Alert(
                source_system="workstations",
                severity=AlertSeverity.CRITICAL,
                message="Ransomware payload executing on workstations",
                is_true_positive=True,
                hour=0,
            ),
            Alert(
                source_system="email_server",
                severity=AlertSeverity.HIGH,
                message="Malicious attachment opened — email_server compromised",
                is_true_positive=True,
                hour=0,
            ),
            Alert(
                source_system="app_server",
                severity=AlertSeverity.MEDIUM,
                message="Unusual CPU spike on app_server",
                is_true_positive=False,  # false alarm
                hour=0,
            ),
        ],
        attacker_progress=0.25,
        attacker_stealth=0.5,
        data_exfiltrated=0.05,
        services_disrupted=1,
        team_stamina=0.9,
        hour=0,
        external_blocked=False,
        management_escalated=False,
    ),
    scoring_weights={
        "data_protection": 0.40,   # protect the data!
        "containment": 0.20,
        "business_continuity": 0.20,
        "forensic": 0.10,
        "sustainability": 0.10,
    },
))


# --- HARD: Advanced Persistent Threat ---
_register(TaskConfig(
    task_id="hard_1",
    description=(
        "SCENARIO: Advanced Persistent Threat (APT)\n"
        "A sophisticated nation-state actor has been inside your network for an "
        "unknown duration. A single alert triggered on the app_server — but this "
        "may be the tip of the iceberg. The attacker is highly stealthy, may have "
        "backdoors on multiple systems, and is actively exfiltrating sensitive data "
        "from the database. Most alerts you see will be false positives.\n"
        "INTEL: Suspected state-sponsored actor. Entry vector unknown. "
        "High evasion capability. Priority: find the full scope before acting."
    ),
    initial_state=IncidentState(
        systems=_make_systems(
            compromised=["app_server", "database"],  # 2 compromised but agent doesn't know about database
            monitoring={},  # no monitoring deployed
        ),
        alerts=[
            Alert(
                source_system="app_server",
                severity=AlertSeverity.MEDIUM,
                message="Anomalous process detected on app_server — possible C2 beacon",
                is_true_positive=True,
                hour=0,
            ),
            Alert(
                source_system="firewall",
                severity=AlertSeverity.LOW,
                message="Routine port scan from external IP",
                is_true_positive=False,
                hour=0,
            ),
        ],
        attacker_progress=0.15,
        attacker_stealth=0.9,  # very stealthy
        data_exfiltrated=0.10,  # already got some data
        services_disrupted=0,
        team_stamina=0.85,
        hour=0,
        external_blocked=False,
        management_escalated=False,
    ),
    scoring_weights={
        "data_protection": 0.35,
        "containment": 0.25,
        "business_continuity": 0.15,
        "forensic": 0.15,   # investigation matters more for APT
        "sustainability": 0.10,
    },
))


def get_task(task_id: str) -> TaskConfig:
    if task_id not in TASKS:
        available = ", ".join(sorted(TASKS.keys()))
        raise KeyError(f"Unknown task_id '{task_id}'. Available: {available}")
    return TASKS[task_id]


def list_tasks() -> list[dict[str, Any]]:
    return [
        {"task_id": c.task_id, "description": c.description, "max_hours": c.max_hours}
        for c in TASKS.values()
    ]
