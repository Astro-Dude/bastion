---
title: Bastion
emoji: 🛡️
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# Bastion: Cybersecurity Incident Response Environment

A research-grade OpenEnv-compatible reinforcement learning environment where an AI agent acts as **Incident Commander** responding to a live cyberattack on a corporate network.

## Why Cybersecurity Incident Response?

Current LLM benchmarks test knowledge recall. Bastion tests something harder: **sequential decision-making under uncertainty where mistakes compound and information is incomplete**.

- **Partial observability** — you don't know which systems are compromised until you investigate
- **Every action has tradeoffs** — isolating a server stops the attacker but kills production
- **Time pressure** — the attacker spreads while you deliberate
- **Cascading consequences** — restoring from a compromised backup re-infects the system
- **False positives** — some alerts are noise, and acting on them wastes resources
- **No single correct answer** — only better trajectories

## Network Topology

```
firewall ─── web_server ─── app_server ─── database ─── backup_server
              (0.6)          (0.8)          (1.0)         (0.9)
                                │
                           file_server ─── email_server
                             (0.7)           (0.4)
                                │              │
                           workstations ───────┘
                             (0.3)
```
Numbers = system criticality (affects scoring). Protecting the database matters 3.3x more than workstations.

## SIEM Alert System

Alerts use professional security metadata with MITRE ATT&CK mapping:

```
[EVT-4624] [high] SMB admin share access from 10.1.1.10 to 10.1.2.20 — 
NTLM auth with service account 'svc_deploy'
           MITRE:Lateral Movement(T1021.002) | src=10.1.1.10→dst=10.1.2.20 | 
           proc=svchost.exe | conf=72%
```

Each alert includes: MITRE technique ID + tactic, source/dest IPs, process name, event ID, confidence score, and file hashes. Templates cover lateral movement (T1021, T1550), exfiltration (T1048, T1041), and false positives (T1078, T1046, T1053).

## Action Space (10 actions x 8 target systems)

| ID | Action | Effect | Tradeoff |
|---|---|---|---|
| 0 | investigate_system | Reveals true compromise state of target | Takes time while attacker moves |
| 1 | isolate_system | Cuts target from network | Kills the service on that system |
| 2 | patch_vulnerability | Fixes vuln, may clean system (30% chance) | Slow, uncertain effectiveness |
| 3 | restore_from_backup | Restores compromised system | **FAILS if backup is also compromised** |
| 4 | analyze_alerts | Reveals true/false positive alert status | Costs team stamina |
| 5 | deploy_monitoring | Adds sensors to target + neighbors | Investment for future turns |
| 6 | escalate_to_management | Gets resources, adds pressure | Scrutiny increases |
| 7 | block_external_traffic | Stops ALL outbound connections | Kills exfiltration AND services |
| 8 | hunt_threat | Proactively search for attacker | May alert the attacker |
| 9 | coordinate_team | Rest and recover stamina | Wastes an hour |

## Attacker Simulation (Adaptive)

Realistic kill chain each hour:
- **Lateral movement** through network adjacency graph (SMB shares, RDP, WinRM, pass-the-hash)
- **Data exfiltration** from database, file_server, email_server, backup_server (HTTPS, DNS tunneling, C2)
- **Backdoor installation** for persistence
- **Integrity degradation** of compromised systems

**The attacker adapts to your strategy:**
| Your Action | Attacker Response |
|---|---|
| Isolate 2+ systems | Panics — accelerates exfiltration on remaining targets |
| Investigate 4+ systems | Goes quiet — reduces activity to avoid detection |
| Block external traffic | Pivots to destruction — degrades systems faster |

## Team Communications (Social Reasoning)

Four IR team members send contextual messages — some helpful, some misleading:
- **Sarah Chen** (Senior Analyst) — usually correct intel, occasionally wrong assumptions
- **Priya Patel** (Junior Analyst) — panics about false positives, urges unnecessary isolations
- **Marcus Webb** (Network Engineer) — pressures you to restore services prematurely
- **James O'Brien** (CISO) — demands speed and status updates, creates time pressure

The agent must decide **who to trust** and resist social pressure to make bad decisions.

## Post-Incident Forensic Report

At episode end, a detailed report card grades the response (A-F) with specific findings:
```
Grades: data_protection=B | threat_containment=A | forensic_coverage=D
CRITICAL: 2 compromised systems were never investigated: app_server, database
WARNING: 1 clean system isolated unnecessarily: firewall
```

## Tasks (3 Scenarios)

| Task | Difficulty | Scenario | Compromised | Stealth | Key Challenge |
|---|---|---|---|---|---|
| easy_1 | Easy | Suspicious External Activity | web_server | 0.4 | Basic triage — clear alerts, single target |
| medium_1 | Medium | Encryption Activity Detected | 3 systems + 1 false positive | 0.5 | Prioritization, distinguishing real from fake |
| hard_1 | Hard | Anomalous Beacon Detected | 2 systems (1 hidden) | 0.9 | Deep investigation, discovering hidden threats |

## Scoring (Criticality-Weighted)

```
35% data protection (1 - data_exfiltrated)
25% containment (1 - active_threats, weighted by system criticality)
20% business continuity (services running, weighted by service criticality)
10% forensic completeness (systems investigated)
10% team sustainability (stamina remaining)
```

Compared against a naive baseline. Score > 0.5 = outperformed baseline.

## Real LLM Benchmark Results

### Gemini 2.0 Flash (full runs)
| Task | Score | Forensic Grades | Strategy |
|---|---|---|---|
| easy_1 | **0.535** | A, A, D, B, F | Contained threat, deployed monitoring, but isolated clean firewall |
| medium_1 | **0.642** | B, A, D, D, F | `analyze_alerts` first, blocked external traffic early, isolated all threats |
| hard_1 | **0.641** | B, A, D, F, F | Isolated database without investigating (risky but correct), blocked traffic |

### Qwen 2.5 72B
| Task | Score | Strategy |
|---|---|---|
| easy_1 | **0.572** | Full investigation sweep, analyzed alerts, deployed monitoring |
| medium_1 | **0.528** | Verified alerts first — learned from confidence scores |
| hard_1 | **0.616** | Found hidden database compromise, checked backup before restoring |

**Key finding**: Both models fail at team stamina management (F grade) and fall for false positives. Gemini plays aggressively, Qwen plays methodically — different strategies, different tradeoffs.

## API Endpoints

Built with OpenEnv `create_app()`:

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/schema` | GET | JSON schemas for Action/Observation/State |
| `/reset` | POST | Reset environment (`task_id` in kwargs) |
| `/step` | POST | Execute action (`{"action": 3, "target_system": 2}`) |
| `/state` | GET | Full ground-truth state |
| `/ws` | WebSocket | Primary communication channel |

## Quick Start

### Run Server Locally
```bash
pip install -r requirements.txt
uvicorn server.app:app --port 7860
```

### Run Inference
```bash
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct
export HF_TOKEN=hf_...
python inference.py
```

### Docker
```bash
docker build -t bastion .
docker run -p 7860:7860 bastion
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `API_BASE_URL` | Yes | OpenAI-compatible API endpoint |
| `MODEL_NAME` | Yes | Model identifier |
| `HF_TOKEN` | Yes | HuggingFace token / API key |
| `LOCAL_IMAGE_NAME` | Optional | Docker image name for `from_docker_image()` |

## What LLMs Learn From This Environment

| Skill Tested | LLM Weakness Exposed |
|---|---|
| Hypothesis formation from SIEM alerts | Takes alerts at face value, doesn't cross-reference |
| Investigate vs act decision | Either over-investigates or acts without evidence |
| False positive discrimination | Can't assess confidence levels — acts on 35% alerts |
| Criticality-based prioritization | Treats all systems equally |
| Social reasoning / filtering team advice | Follows junior analyst's panic, complies with authority pressure |
| Adapting to adaptive attacker | Doesn't notice attacker changing behavior after isolations |
| Resource management | Ignores team stamina — every test run ends at F grade |

See [DESIGN.md](DESIGN.md) for the full technical design document.

## Technical Details

- **OpenEnv spec**: Extends `Environment[Action, Observation, State]` from `openenv-core`
- **Deterministic**: Same `task_id` → same initial state and RNG seed
- **Episode**: 12 steps (hours) or until total data breach
- **Baseline**: Naive rotation policy (investigate → isolate → monitor → patch)
- **MITRE ATT&CK**: 12+ technique IDs across lateral movement, exfiltration, and false positive categories
- **Dense reward**: 5-component criticality-weighted per-step signal + catastrophic penalties
