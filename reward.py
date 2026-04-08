"""
Bastion: Cybersecurity Incident Response — Reward & Scoring

Three layers:
  1. Dense step reward — criticality-weighted containment and protection
  2. Penalties — catastrophic breach, total service outage, team burnout
  3. Final score — holistic incident response quality (0-1)
"""

from __future__ import annotations

from models import IncidentState, SERVICE_SYSTEMS, NUM_SYSTEMS


# ---------------------------------------------------------------------------
# Step-level dense reward (criticality-weighted)
# ---------------------------------------------------------------------------

def compute_step_reward(
    prev: IncidentState,
    curr: IncidentState,
    stamina_cost: float,
) -> float:
    """Dense reward weighted by system criticality."""

    # Containment: weighted by criticality (protecting database > workstations)
    prev_threat = sum(
        s.criticality for s in prev.systems if s.compromised and not s.isolated
    )
    curr_threat = sum(
        s.criticality for s in curr.systems if s.compromised and not s.isolated
    )
    total_criticality = sum(s.criticality for s in curr.systems) or 1.0
    delta_containment = (prev_threat - curr_threat) / total_criticality

    # Data protection: unchanged (already global)
    delta_exfil = curr.data_exfiltrated - prev.data_exfiltrated

    # Service continuity: weighted by service criticality
    prev_disruption = sum(
        s.criticality for s in prev.systems
        if s.name in SERVICE_SYSTEMS and (s.isolated or s.integrity < 0.3)
    )
    curr_disruption = sum(
        s.criticality for s in curr.systems
        if s.name in SERVICE_SYSTEMS and (s.isolated or s.integrity < 0.3)
    )
    service_crit = sum(s.criticality for s in curr.systems if s.name in SERVICE_SYSTEMS) or 1.0
    delta_disruption = (curr_disruption - prev_disruption) / service_crit

    # Investigation progress
    prev_investigated = sum(1 for s in prev.systems if s.investigated)
    curr_investigated = sum(1 for s in curr.systems if s.investigated)
    delta_investigation = (curr_investigated - prev_investigated) / NUM_SYSTEMS

    reward = (
        0.30 * delta_containment
        + 0.30 * (-delta_exfil)
        + 0.20 * (-delta_disruption)
        + 0.10 * delta_investigation
        - 0.10 * stamina_cost
    )
    return reward


# ---------------------------------------------------------------------------
# Penalties
# ---------------------------------------------------------------------------

def compute_penalties(state: IncidentState) -> float:
    penalty = 0.0

    if state.data_exfiltrated > 0.8:
        penalty -= 1.0

    services_down = sum(
        1 for s in state.systems
        if s.name in SERVICE_SYSTEMS and (s.isolated or s.integrity < 0.3)
    )
    if services_down >= len(SERVICE_SYSTEMS):
        penalty -= 0.5

    if state.team_stamina <= 0.05:
        penalty -= 0.3

    return penalty


# ---------------------------------------------------------------------------
# Final score (criticality-weighted)
# ---------------------------------------------------------------------------

def compute_final_score(state: IncidentState) -> float:
    """Holistic score weighted by system criticality. Returns [0, 1]."""
    data_protection = 1.0 - state.data_exfiltrated

    # Containment weighted by criticality
    active_threat = sum(
        s.criticality for s in state.systems if s.compromised and not s.isolated
    )
    total_crit = sum(s.criticality for s in state.systems) or 1.0
    containment = 1.0 - (active_threat / total_crit)

    # Business continuity weighted by service criticality
    services_intact_weighted = sum(
        s.criticality for s in state.systems
        if s.name in SERVICE_SYSTEMS and not s.isolated and s.integrity > 0.3
    )
    total_service_crit = sum(
        s.criticality for s in state.systems if s.name in SERVICE_SYSTEMS
    ) or 0.01
    business_continuity = services_intact_weighted / total_service_crit

    forensic = sum(1 for s in state.systems if s.investigated) / NUM_SYSTEMS
    sustainability = state.team_stamina

    score = (
        0.35 * data_protection
        + 0.25 * containment
        + 0.20 * business_continuity
        + 0.10 * forensic
        + 0.10 * sustainability
    )
    return max(0.0, min(1.0, score))


def compute_task_weighted_score(
    state: IncidentState,
    weights: dict[str, float] | None = None,
) -> float:
    if weights is None:
        return compute_final_score(state)

    data_protection = 1.0 - state.data_exfiltrated

    active_threat = sum(
        s.criticality for s in state.systems if s.compromised and not s.isolated
    )
    total_crit = sum(s.criticality for s in state.systems) or 1.0
    containment = 1.0 - (active_threat / total_crit)

    services_intact_weighted = sum(
        s.criticality for s in state.systems
        if s.name in SERVICE_SYSTEMS and not s.isolated and s.integrity > 0.3
    )
    total_service_crit = sum(
        s.criticality for s in state.systems if s.name in SERVICE_SYSTEMS
    ) or 0.01
    business_continuity = services_intact_weighted / total_service_crit

    forensic = sum(1 for s in state.systems if s.investigated) / NUM_SYSTEMS
    sustainability = state.team_stamina

    score = (
        weights.get("data_protection", 0.35) * data_protection
        + weights.get("containment", 0.25) * containment
        + weights.get("business_continuity", 0.20) * business_continuity
        + weights.get("forensic", 0.10) * forensic
        + weights.get("sustainability", 0.10) * sustainability
    )
    return max(0.0, min(1.0, score))


def compute_baseline_comparison(
    agent_state: IncidentState,
    baseline_state: IncidentState,
    weights: dict[str, float] | None = None,
) -> float:
    agent_score = compute_task_weighted_score(agent_state, weights)
    baseline_score = compute_task_weighted_score(baseline_state, weights)
    diff = agent_score - baseline_score
    return max(0.0, min(1.0, (diff + 1.0) / 2.0))
