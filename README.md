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

A live cyberattack is the perfect stress test because:
- **Partial observability is real** — you don't know what the attacker has done until you investigate
- **Every action has tradeoffs** — isolating a server stops the attacker but kills production
- **Time pressure** — the attacker spreads while you deliberate
- **Cascading consequences** — wrong moves make things worse (restoring from compromised backup re-infects systems)
- **No single correct answer** — only better trajectories

## HuggingFace Space

> **Space URL**: _[To be updated after deployment]_

## Environment Design

### Network (8 Systems)
```
firewall ─── web_server ─── app_server ─── database ─── backup_server
                                │
                           file_server ─── email_server
                                │              │
                           workstations ───────┘
```

Each system has: `compromised` (hidden), `isolated`, `investigated`, `integrity`, `monitoring_level`, `patched`

### Observation (Partial Observability)
- **Compromise status is UNKNOWN** unless the system has been investigated
- **Alerts may be false positives** — `analyze_alerts` reveals which are real
- **Data exfiltration is estimated** with noise and delay
- **Attacker progress is invisible** — you only see its effects

### Action Space (10 actions × 8 target systems)
| ID | Action | Effect | Tradeoff |
|---|---|---|---|
| 0 | investigate_system | Reveals true state of target | Takes time while attacker moves |
| 1 | isolate_system | Cuts target from network | Kills the service on that system |
| 2 | patch_vulnerability | Fixes vuln, may clean system | Slow, uncertain effectiveness |
| 3 | restore_from_backup | Restores compromised system | FAILS if backup is also compromised |
| 4 | analyze_alerts | Reveals true/false positive alerts | Costs team stamina |
| 5 | deploy_monitoring | Adds sensors to target + neighbors | Investment for future turns |
| 6 | escalate_to_management | Gets resources, adds pressure | Scrutiny increases |
| 7 | block_external_traffic | Stops ALL outbound connections | Kills exfiltration AND services |
| 8 | hunt_threat | Proactively search for attacker | May alert the attacker |
| 9 | coordinate_team | Rest and recover stamina | Wastes an hour |

### Attacker Simulation
Realistic kill chain:
- **Lateral movement** through network adjacency graph
- **Data exfiltration** from database, file_server, email_server, backup_server
- **Backdoor installation** for persistence
- **Integrity degradation** of compromised systems
- **Adapts**: slows when detected, accelerates when stealthy

### Tasks (3 Scenarios)

| Task | Difficulty | Scenario | Compromised | Attacker Stealth |
|---|---|---|---|---|
| easy_1 | Easy | Script Kiddie | web_server | 0.4 (noisy) |
| medium_1 | Medium | Ransomware Outbreak | file_server, workstations, email | 0.5 |
| hard_1 | Hard | APT (nation-state) | app_server, database (hidden) | 0.9 (very stealthy) |

### Scoring
```
35% data protection (1 - data_exfiltrated)
25% containment (1 - attacker_progress)
20% business continuity (services still running)
10% forensic completeness (systems investigated)
10% team sustainability (stamina remaining)
```

Compared against a naive baseline. Score > 0.5 = outperformed baseline.

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
export IMAGE_NAME=bastion
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
| `IMAGE_NAME` | Yes | Docker image name for `from_docker_image()` |

## What LLMs Learn From This Environment

| Skill | How It's Tested |
|---|---|
| Hypothesis formation | Must interpret alerts + investigate to form attack theory |
| Information vs action balance | Investigate first or act immediately? |
| Risk assessment | Weigh "cost of being wrong" for each action |
| Prioritization | Multiple systems under attack, one action per hour |
| Adaptive strategy | Attack evolves — initial plan must be revised |
| Resource management | Team stamina depletes, must coordinate rest |

See [DESIGN.md](DESIGN.md) for the full technical design document.

## Technical Details

- **OpenEnv spec**: Extends `Environment[Action, Observation, State]` from `openenv-core`
- **Deterministic**: Same `task_id` → same initial state and RNG seed
- **Episode**: 12 steps (hours) or until total data breach
- **Baseline**: Naive rotation policy (investigate → isolate → monitor → patch)
- **Dense reward**: Per-step signal for containment, data protection, service continuity
