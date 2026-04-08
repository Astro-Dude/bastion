"""
Bastion: Cybersecurity Incident Response — Transition Dynamics

Simulates a realistic cyberattack kill chain and defender response.

Attacker behavior:
  - Lateral movement through network adjacency graph
  - Data exfiltration from data-holding systems
  - Privilege escalation over time
  - Backdoor installation for persistence
  - Adapts to defender actions (slows when detected)

Defender actions:
  - Each action costs team stamina and time
  - Some actions are targeted (affect a specific system)
  - Some are global (affect the whole network)
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Dict, List, Tuple

from models import (
    ActionType,
    Alert,
    AlertSeverity,
    DATA_SYSTEMS,
    IncidentState,
    NETWORK_ADJACENCY,
    SERVICE_SYSTEMS,
    SYSTEM_NAMES,
    SystemState,
)


# ---------------------------------------------------------------------------
# Network topology (IPs, hostnames)
# ---------------------------------------------------------------------------

SYSTEM_IPS: Dict[str, str] = {
    "web_server": "10.1.1.10",
    "app_server": "10.1.2.20",
    "database": "10.1.3.30",
    "file_server": "10.1.4.40",
    "email_server": "10.1.5.50",
    "workstations": "10.1.6.100",
    "backup_server": "10.1.7.70",
    "firewall": "10.0.0.1",
}

C2_IPS = ["198.51.100.23", "203.0.113.42", "192.0.2.117", "45.77.65.211"]

# ---------------------------------------------------------------------------
# SIEM alert templates — MITRE ATT&CK mapped
# ---------------------------------------------------------------------------

LATERAL_MOVEMENT_ALERTS = [
    {
        "mitre_technique": "T1021.002", "mitre_tactic": "Lateral Movement",
        "process_name": "svchost.exe", "event_id": "EVT-4624",
        "msg": "SMB admin share access from {src_ip} to {dst_ip} — NTLM auth with service account 'svc_deploy'",
    },
    {
        "mitre_technique": "T1021.001", "mitre_tactic": "Lateral Movement",
        "process_name": "mstsc.exe", "event_id": "EVT-4648",
        "msg": "RDP session initiated from {src_ip} to {dst_ip} using explicit credentials (user: admin$)",
    },
    {
        "mitre_technique": "T1021.006", "mitre_tactic": "Lateral Movement",
        "process_name": "winrm.cmd", "event_id": "EVT-4688",
        "msg": "WinRM remote command execution from {src_ip} on {dst} — encoded PowerShell payload detected",
    },
    {
        "mitre_technique": "T1550.002", "mitre_tactic": "Lateral Movement",
        "process_name": "lsass.exe", "event_id": "EVT-4624",
        "msg": "Pass-the-hash authentication from {src_ip} to {dst_ip} — NTLMv2 with non-interactive logon type 3",
    },
]

EXFILTRATION_ALERTS = [
    {
        "mitre_technique": "T1048.003", "mitre_tactic": "Exfiltration",
        "process_name": "curl.exe", "event_id": "EVT-5156",
        "msg": "Large outbound HTTPS transfer from {sys} ({sys_ip}) to {ext_ip} — {size}MB over port 443",
    },
    {
        "mitre_technique": "T1048.001", "mitre_tactic": "Exfiltration",
        "process_name": "dns.exe", "event_id": "EVT-5158",
        "msg": "High-entropy DNS TXT queries from {sys} to {ext_ip} — possible DNS tunneling ({count} queries/min)",
    },
    {
        "mitre_technique": "T1041", "mitre_tactic": "Exfiltration",
        "process_name": "svchost.exe", "event_id": "EVT-5156",
        "msg": "C2 channel data exfiltration from {sys} ({sys_ip}) — beacon interval 60s to {ext_ip}:8443",
    },
]

FALSE_POSITIVE_ALERTS = [
    {
        "mitre_technique": "T1078", "mitre_tactic": "Initial Access",
        "process_name": "sshd", "event_id": "EVT-4625",
        "msg": "Multiple failed SSH logins on {sys} from {ext_ip} — likely automated scanner (15 attempts/min)",
        "confidence": 0.25,
    },
    {
        "mitre_technique": "T1046", "mitre_tactic": "Discovery",
        "process_name": "nmap", "event_id": "EVT-5156",
        "msg": "Sequential port scan detected targeting {sys} ({sys_ip}) from {ext_ip} — ports 1-1024",
        "confidence": 0.20,
    },
    {
        "mitre_technique": "T1053.005", "mitre_tactic": "Persistence",
        "process_name": "schtasks.exe", "event_id": "EVT-4698",
        "msg": "Scheduled task created on {sys}: 'WindowsUpdateCheck' — runs daily at 02:00 (likely benign)",
        "confidence": 0.15,
    },
    {
        "mitre_technique": "T1059.001", "mitre_tactic": "Execution",
        "process_name": "powershell.exe", "event_id": "EVT-4688",
        "msg": "PowerShell execution on {sys} by SYSTEM — encoded command matches monitoring agent signature",
        "confidence": 0.30,
    },
    {
        "mitre_technique": "T1071.001", "mitre_tactic": "Command and Control",
        "process_name": "chrome.exe", "event_id": "EVT-5156",
        "msg": "Periodic HTTPS beacon from {sys} to {ext_ip}:443 — pattern consistent with browser keepalive",
        "confidence": 0.20,
    },
]


def _make_file_hash(seed: str) -> str:
    """Generate a deterministic fake file hash from a seed string."""
    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Attacker simulation
# ---------------------------------------------------------------------------

def attacker_turn(state: IncidentState, rng: random.Random) -> List[Alert]:
    """
    Simulate one hour of attacker activity. Returns new alerts generated.
    The attacker:
      1. Attempts lateral movement to adjacent systems
      2. Exfiltrates data from compromised data systems
      3. Installs backdoors on compromised systems
      4. Degrades integrity of compromised systems
    """
    alerts: List[Alert] = []
    speed = state.attacker_stealth  # higher stealth = more effective

    # --- Lateral movement ---
    compromised_names = [
        s.name for s in state.systems
        if s.compromised and not s.isolated
    ]

    for src_name in compromised_names:
        neighbors = NETWORK_ADJACENCY.get(src_name, [])
        for neighbor_name in neighbors:
            target = state.get_system(neighbor_name)
            if target.compromised or target.isolated:
                continue

            # Chance of spreading depends on stealth, monitoring, and patching
            base_chance = 0.25 * speed
            if target.patched:
                base_chance *= 0.3
            if target.monitoring_level >= 2:
                base_chance *= 0.5

            if rng.random() < base_chance:
                target.compromised = True
                state.attacker_progress = min(1.0, state.attacker_progress + 0.08)

                # Generate SIEM-enriched alert (may or may not be detected)
                detect_chance = 0.3 + target.monitoring_level * 0.2
                if rng.random() < detect_chance:
                    t = rng.choice(LATERAL_MOVEMENT_ALERTS)
                    src_ip = SYSTEM_IPS.get(src_name, "10.0.0.1")
                    dst_ip = SYSTEM_IPS.get(neighbor_name, "10.0.0.2")
                    conf = min(0.95, 0.45 + target.monitoring_level * 0.15 + rng.uniform(-0.05, 0.05))
                    alerts.append(Alert(
                        source_system=neighbor_name,
                        severity=AlertSeverity.HIGH,
                        message=t["msg"].format(src_ip=src_ip, dst_ip=dst_ip, dst=neighbor_name),
                        is_true_positive=True,
                        hour=state.hour,
                        source_ip=src_ip,
                        dest_ip=dst_ip,
                        mitre_technique=t["mitre_technique"],
                        mitre_tactic=t["mitre_tactic"],
                        process_name=t["process_name"],
                        event_id=t["event_id"],
                        confidence=round(conf, 2),
                        file_hash=_make_file_hash(f"{state.hour}{neighbor_name}{src_name}"),
                    ))

    # --- Data exfiltration ---
    if not state.external_blocked:
        for s in state.systems:
            if s.compromised and not s.isolated and s.name in DATA_SYSTEMS:
                exfil_rate = 0.08 * speed * s.integrity
                state.data_exfiltrated = min(1.0, state.data_exfiltrated + exfil_rate)

                if rng.random() < 0.25 + s.monitoring_level * 0.15:
                    t = rng.choice(EXFILTRATION_ALERTS)
                    sys_ip = SYSTEM_IPS.get(s.name, "10.0.0.1")
                    ext_ip = rng.choice(C2_IPS)
                    size = rng.randint(50, 500)
                    count = rng.randint(80, 300)
                    conf = min(0.95, 0.50 + s.monitoring_level * 0.15 + rng.uniform(-0.05, 0.05))
                    alerts.append(Alert(
                        source_system=s.name,
                        severity=AlertSeverity.CRITICAL,
                        message=t["msg"].format(sys=s.name, sys_ip=sys_ip, ext_ip=ext_ip, size=size, count=count),
                        is_true_positive=True,
                        hour=state.hour,
                        source_ip=sys_ip,
                        dest_ip=ext_ip,
                        mitre_technique=t["mitre_technique"],
                        mitre_tactic=t["mitre_tactic"],
                        process_name=t["process_name"],
                        event_id=t["event_id"],
                        confidence=round(conf, 2),
                    ))

    # --- Backdoor installation ---
    for s in state.systems:
        if s.compromised and not s.isolated and not s.has_backdoor:
            if rng.random() < 0.15 * speed:
                s.has_backdoor = True
                state.attacker_progress = min(1.0, state.attacker_progress + 0.03)

    # --- Integrity degradation ---
    for s in state.systems:
        if s.compromised and not s.isolated:
            s.integrity = max(0.0, s.integrity - rng.uniform(0.02, 0.08))

    # --- False positive alerts (noise) — SIEM-enriched ---
    num_false = rng.randint(0, 2)
    for _ in range(num_false):
        fake_sys = rng.choice(SYSTEM_NAMES)
        severity = rng.choice([AlertSeverity.LOW, AlertSeverity.MEDIUM])
        t = rng.choice(FALSE_POSITIVE_ALERTS)
        sys_ip = SYSTEM_IPS.get(fake_sys, "10.0.0.1")
        ext_ip = rng.choice(C2_IPS)
        alerts.append(Alert(
            source_system=fake_sys,
            severity=severity,
            message=t["msg"].format(sys=fake_sys, sys_ip=sys_ip, ext_ip=ext_ip),
            is_true_positive=False,
            hour=state.hour,
            source_ip=ext_ip,
            dest_ip=sys_ip,
            mitre_technique=t["mitre_technique"],
            mitre_tactic=t["mitre_tactic"],
            process_name=t["process_name"],
            event_id=t["event_id"],
            confidence=round(t["confidence"] + rng.uniform(-0.05, 0.05), 2),
        ))

    # --- Attacker stealth decays slightly each hour (they get bolder) ---
    state.attacker_stealth = max(0.1, state.attacker_stealth - 0.03)

    return alerts


# ---------------------------------------------------------------------------
# Defender actions
# ---------------------------------------------------------------------------

STAMINA_COSTS = {
    ActionType.INVESTIGATE_SYSTEM: 0.08,
    ActionType.ISOLATE_SYSTEM: 0.05,
    ActionType.PATCH_VULNERABILITY: 0.10,
    ActionType.RESTORE_FROM_BACKUP: 0.12,
    ActionType.ANALYZE_ALERTS: 0.08,
    ActionType.DEPLOY_MONITORING: 0.06,
    ActionType.ESCALATE_TO_MANAGEMENT: 0.02,
    ActionType.BLOCK_EXTERNAL_TRAFFIC: 0.03,
    ActionType.HUNT_THREAT: 0.12,
    ActionType.COORDINATE_TEAM: -0.25,  # recovers stamina
}


def apply_action(
    state: IncidentState,
    action: int,
    target_idx: int,
    rng: random.Random,
) -> Tuple[float, bool]:
    """
    Apply a defender action. Returns (stamina_cost, alerts_accurate).
    alerts_accurate is True if analyze_alerts was used this turn.
    """
    a = ActionType(action)
    target = state.get_system_by_idx(target_idx)
    alerts_accurate = False

    # Apply stamina cost
    cost = STAMINA_COSTS[a]
    state.team_stamina = max(0.0, min(1.0, state.team_stamina + (cost if cost < 0 else -cost)))

    # Effectiveness scales with stamina (tired team makes mistakes)
    effectiveness = 0.5 + 0.5 * state.team_stamina

    if a == ActionType.INVESTIGATE_SYSTEM:
        # Reveals true state of the target system
        target.investigated = True
        # Investigating a compromised system reduces attacker stealth
        if target.compromised:
            state.attacker_stealth = max(0.0, state.attacker_stealth - 0.15)

    elif a == ActionType.ISOLATE_SYSTEM:
        target.isolated = True
        # If it was a service, it's now disrupted
        if target.name in SERVICE_SYSTEMS:
            state.services_disrupted = sum(
                1 for s in state.systems
                if s.name in SERVICE_SYSTEMS and (s.isolated or s.integrity < 0.3)
            )

    elif a == ActionType.PATCH_VULNERABILITY:
        if not target.isolated:
            target.patched = True
            # If compromised, patching has a chance to clean the system
            if target.compromised and rng.random() < 0.3 * effectiveness:
                target.compromised = False
                target.has_backdoor = False

    elif a == ActionType.RESTORE_FROM_BACKUP:
        backup = state.get_system("backup_server")
        if not backup.compromised or backup.investigated:
            # Restore the target from backup
            if rng.random() < 0.7 * effectiveness:
                target.compromised = False
                target.has_backdoor = False
                target.integrity = min(1.0, target.integrity + 0.5)
                target.isolated = False  # bring it back online
            # If backup is compromised and not investigated, restore might fail silently
        elif backup.compromised and not backup.investigated:
            # Restoring from compromised backup — re-infects the system!
            target.compromised = True
            target.has_backdoor = True

    elif a == ActionType.ANALYZE_ALERTS:
        alerts_accurate = True
        # Also slightly reduces attacker stealth (you understand the attack better)
        state.attacker_stealth = max(0.0, state.attacker_stealth - 0.05)

    elif a == ActionType.DEPLOY_MONITORING:
        target.monitoring_level = min(3, target.monitoring_level + 1)
        # Better monitoring on all adjacent systems too
        neighbors = NETWORK_ADJACENCY.get(target.name, [])
        for n in neighbors:
            ns = state.get_system(n)
            ns.monitoring_level = min(3, ns.monitoring_level + 1)

    elif a == ActionType.ESCALATE_TO_MANAGEMENT:
        if not state.management_escalated:
            state.management_escalated = True
            # Gives resources but adds pressure
            state.team_stamina = min(1.0, state.team_stamina + 0.15)
            state.management_pressure = 0.3
        else:
            # Already escalated — just increases pressure
            state.management_pressure = min(1.0, state.management_pressure + 0.2)

    elif a == ActionType.BLOCK_EXTERNAL_TRAFFIC:
        state.external_blocked = True
        # Stops exfiltration but disrupts services
        for s in state.systems:
            if s.name in SERVICE_SYSTEMS and not s.isolated:
                s.integrity = max(0.0, s.integrity - 0.15)

    elif a == ActionType.HUNT_THREAT:
        # Proactive threat hunting on target system
        if target.compromised and not target.investigated:
            # Chance to discover compromise
            discover_chance = 0.5 * effectiveness + target.monitoring_level * 0.1
            if rng.random() < discover_chance:
                target.investigated = True
                state.attacker_stealth = max(0.0, state.attacker_stealth - 0.1)
        elif not target.compromised and not target.investigated:
            # Hunting a clean system still marks it as investigated
            if rng.random() < 0.6 * effectiveness:
                target.investigated = True

    elif a == ActionType.COORDINATE_TEAM:
        # Already handled by negative stamina cost above
        # Also slightly reduces management pressure
        state.management_pressure = max(0.0, state.management_pressure - 0.1)

    return abs(cost), alerts_accurate


# ---------------------------------------------------------------------------
# Full step: defender acts, then attacker moves
# ---------------------------------------------------------------------------

def step_dynamics(
    state: IncidentState,
    action: int,
    target_idx: int,
    rng: random.Random,
) -> Tuple[float, bool]:
    """
    Full transition: defender acts, then attacker moves, then time advances.
    Returns (stamina_cost, alerts_accurate).
    """
    # 1. Defender acts
    stamina_cost, alerts_accurate = apply_action(state, action, target_idx, rng)

    # 2. Attacker moves
    new_alerts = attacker_turn(state, rng)
    state.alerts.extend(new_alerts)

    # 3. Management pressure increases over time if escalated
    if state.management_escalated:
        state.management_pressure = min(1.0, state.management_pressure + 0.05)

    # 4. Update services disrupted count
    state.services_disrupted = sum(
        1 for s in state.systems
        if s.name in SERVICE_SYSTEMS and (s.isolated or s.integrity < 0.3)
    )

    # 5. Advance time
    state.hour += 1
    state.step_count += 1

    return stamina_cost, alerts_accurate
