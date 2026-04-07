"""
Bastion: Cybersecurity Incident Response — Reward & Scoring

Three layers:
  1. Dense step reward — encourages containment, discourages wasted actions
  2. Penalties — catastrophic breach, total service outage, team burnout
  3. Final score — holistic incident response quality (0-1)
"""

from __future__ import annotations

from models import IncidentState, SERVICE_SYSTEMS, NUM_SYSTEMS


# ---------------------------------------------------------------------------
# Step-level dense reward
# ---------------------------------------------------------------------------

def compute_step_reward(
    prev: IncidentState,
    curr: IncidentState,
    stamina_cost: float,
) -> float:
    """Dense reward based on containment progress, data protection, and cost."""

    # Containment: fewer active compromised systems is good
    prev_active = sum(1 for s in prev.systems if s.compromised and not s.isolated)
    curr_active = sum(1 for s in curr.systems if s.compromised and not s.isolated)
    delta_containment = (prev_active - curr_active) / max(NUM_SYSTEMS, 1)

    # Data protection: less exfiltration is good
    delta_exfil = curr.data_exfiltrated - prev.data_exfiltrated

    # Service continuity
    prev_disrupted = prev.services_disrupted
    curr_disrupted = curr.services_disrupted
    delta_disruption = (curr_disrupted - prev_disrupted) / len(SERVICE_SYSTEMS)

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
    """Non-positive penalty for catastrophic outcomes."""
    penalty = 0.0

    # Catastrophic data breach (>80% exfiltrated)
    if state.data_exfiltrated > 0.8:
        penalty -= 1.0

    # All critical services down
    services_down = sum(
        1 for s in state.systems
        if s.name in SERVICE_SYSTEMS and (s.isolated or s.integrity < 0.3)
    )
    if services_down >= len(SERVICE_SYSTEMS):
        penalty -= 0.5

    # Team burnout
    if state.team_stamina <= 0.05:
        penalty -= 0.3

    return penalty


# ---------------------------------------------------------------------------
# Final score
# ---------------------------------------------------------------------------

def compute_final_score(state: IncidentState) -> float:
    """
    Holistic score of incident response quality. Returns [0, 1].

    Components:
      35% data protection (1 - data_exfiltrated)
      25% containment (1 - attacker_progress)
      20% business continuity (services intact / total)
      10% forensic completeness (systems investigated / total)
      10% team sustainability (stamina remaining)
    """
    data_protection = 1.0 - state.data_exfiltrated
    containment = 1.0 - state.attacker_progress
    services_intact = sum(
        1 for s in state.systems
        if s.name in SERVICE_SYSTEMS and not s.isolated and s.integrity > 0.3
    )
    business_continuity = services_intact / len(SERVICE_SYSTEMS)
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
    """Task-specific scoring with custom weights."""
    if weights is None:
        return compute_final_score(state)

    data_protection = 1.0 - state.data_exfiltrated
    containment = 1.0 - state.attacker_progress
    services_intact = sum(
        1 for s in state.systems
        if s.name in SERVICE_SYSTEMS and not s.isolated and s.integrity > 0.3
    )
    business_continuity = services_intact / len(SERVICE_SYSTEMS)
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
    """Agent vs baseline, mapped to [0, 1]. 0.5 = tied."""
    agent_score = compute_task_weighted_score(agent_state, weights)
    baseline_score = compute_task_weighted_score(baseline_state, weights)
    diff = agent_score - baseline_score
    return max(0.0, min(1.0, (diff + 1.0) / 2.0))
