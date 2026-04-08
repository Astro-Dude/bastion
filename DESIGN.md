# Bastion: Cybersecurity Incident Response Environment

## Why This Project Exists

### The Problem with Current LLM Evaluation

Most LLM benchmarks test **knowledge recall** — trivia, coding syntax, math formulas. But real-world intelligence requires something harder: **making sequential decisions under uncertainty where early mistakes compound and information is incomplete**.

Current LLMs fail at this because:
- They **overreact** to the most recent information (recency bias)
- They **can't plan ahead** — they optimize for the immediate step, not the trajectory
- They **ignore opportunity cost** — doing action A means you can't do action B
- They **don't update beliefs properly** when new evidence contradicts their hypothesis
- They **struggle with partial information** — they either hallucinate certainty or become paralyzed

### Why Cybersecurity Incident Response?

A live cyberattack is the **perfect stress test** for an AI agent because:

1. **Partial observability is real** — you genuinely don't know what the attacker has done. You see alerts, but alerts can be false positives. You see logs, but the attacker may have tampered with them. You must form hypotheses and test them.

2. **Every action has tradeoffs** — isolating a server stops the attacker but kills production. Alerting your team is necessary but the attacker might notice. Investigating takes time while the attacker is still moving.

3. **Time pressure creates tension** — the attacker spreads laterally while you deliberate. Taking too long is itself a failure mode.

4. **Cascading consequences** — if you don't isolate a compromised database server, the attacker pivots from it to the backup server. If you restore from a compromised backup, you re-infect the system.

5. **No single correct answer** — there are better and worse trajectories, but the optimal strategy depends on what the attacker is doing, which you can only partially observe.

---

## How This Trains LLMs (The RL Pipeline)

### Step 1: Environment as Gym

```
┌──────────────┐     observation (JSON)      ┌──────────────┐
│              │ ───────────────────────────► │              │
│   Bastion    │                              │   LLM Agent  │
│  (this env)  │ ◄─────────────────────────── │  (policy π)  │
│              │     action (0-9, target 0-7) │              │
└──────────────┘                              └──────────────┘
        │                                            │
        │  reward signal                             │
        └────────────────────────────────────────────┘
```

The LLM is the **policy** (π). It receives a SIEM alert queue and system status, reasons about the situation, and picks an action. The environment returns a reward. Over many episodes, the LLM generates trajectories:

```
Episode 1: obs₀ → investigate(app_server) → r₁, obs₁ → isolate(database) → r₂, ... → score = 0.3
Episode 2: obs₀ → analyze_alerts → r₁, obs₁ → investigate(database) → r₂, ... → score = 0.8
```

### Step 2: Generating Training Signal

**For RLHF / DPO (preference learning):**
- Run the LLM 100 times on the same scenario
- Trajectories with high scores → "preferred"
- Trajectories with low scores → "rejected"
- Train a reward model on these preferences
- Fine-tune the LLM to prefer better trajectories

**For PPO / Online RL:**
- The dense per-step reward directly guides policy gradient updates
- The LLM learns: "when I see high data_exfiltrated + low investigation_progress, I should investigate before isolating"

**For Eval / Benchmarking:**
- Run different LLMs through identical scenarios (deterministic seeds)
- Compare their `comparison_score` against the baseline
- Publish results: "GPT-4o scores 0.72, Llama-3-70B scores 0.58, Qwen-72B scores 0.55"

### Step 3: What the LLM Actually Learns

| Skill | How It's Tested | Why LLMs Currently Fail |
|---|---|---|
| **Hypothesis formation** | Must interpret SIEM alerts with MITRE ATT&CK tags, IPs, process names to form attack theory | LLMs take alerts at face value, don't cross-reference indicators |
| **Information gathering vs action** | Must decide when to investigate vs when to act | LLMs either investigate forever or act too quickly |
| **Risk assessment** | Must weigh "cost of being wrong" for each action — isolating a clean server wastes service uptime | LLMs don't model downside risk well |
| **Prioritization** | Multiple systems under attack, limited actions per turn — database (criticality=1.0) matters more than workstations (0.3) | LLMs try to do everything at once or focus on the wrong thing |
| **Adaptive strategy** | Attacker changes behavior in response to defender actions (accelerates when cornered, goes quiet when hunted) | LLMs anchor on their first hypothesis |
| **Signal vs noise** | False positive alerts (35% confidence) mixed with real alerts (82% confidence) | LLMs can't distinguish reliable from unreliable information |
| **Social reasoning** | Team members send messages with opinions, requests, and pressure — some correct, some wrong, some manipulative | LLMs can't filter unreliable social input from expert advice |
| **Resisting pressure** | CISO demands speed, junior analyst panics about false positives, network engineer complains about downtime | LLMs comply with authority figures even when the advice is bad |
| **Resource management** | Team stamina depletes, must strategically rest the team | LLMs ignore resource constraints |

---

## Environment Design

### The Scenario

You are the **Incident Commander** at a mid-size tech company. Your network has been breached. An attacker is inside your network, moving laterally, exfiltrating data, and escalating privileges.

You have a 12-step window (each step = 1 hour of incident response) to contain the breach, minimize data loss, and restore operations.

### Network Topology

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
Numbers in parentheses = system criticality (affects scoring weight).

### State (What's Really Happening)

Each of the 8 systems has:
- `compromised`: bool (is the attacker on this system?)
- `isolated`: bool (have we cut it off from the network?)
- `investigated`: bool (have we forensically analyzed it?)
- `has_backdoor`: bool (has the attacker installed persistence?)
- `integrity`: float (0-1, how intact is the data/service?)
- `criticality`: float (how important is this system?)
- `monitoring_level`: int (0-3, sensor coverage)
- `patched`: bool (has this system been patched?)

Global state:
- `attacker_progress`: float (0-1, how much of their objective achieved)
- `attacker_stealth`: float (0-1, how hidden the attacker remains)
- `data_exfiltrated`: float (0-1, how much sensitive data stolen)
- `team_stamina`: float (0-1, team fatigue level)
- `alert_queue`: list of SIEM alerts (some real, some false positives)

### Observation (What the Agent Sees — Partial Observability)

The agent does NOT see the true state. Instead:
- **Compromise status is UNKNOWN** until a system is investigated — shows `compromised: ?`
- **Alerts contain false positives** — the agent doesn't know which are real
- **Alert confidence varies** — real alerts tend to have higher confidence (72-94%) but false positives can look convincing (15-35%)
- **Data exfiltration is estimated** with Gaussian noise
- **Attacker progress is invisible** — you only see its effects
- `analyze_alerts` reveals true/false positive status for one step

### SIEM Alert System

Alerts are enriched with professional security metadata:

```
[EVT-4624] [high] SMB admin share access from 10.1.1.10 to 10.1.2.20 — 
NTLM auth with service account 'svc_deploy'
           MITRE:Lateral Movement(T1021.002) | src=10.1.1.10→dst=10.1.2.20 | 
           proc=svchost.exe | conf=72%
```

Each alert includes:
- **MITRE ATT&CK** technique ID and tactic (e.g., T1021.002 = SMB/Windows Admin Shares)
- **Source/destination IPs** from the internal network map
- **Process name** that triggered the alert
- **Event ID** from the detection engine
- **Confidence score** (higher = more likely real)
- **File hashes** when applicable (SHA-256)

Alert templates cover:
- **Lateral movement**: SMB share access, RDP sessions, WinRM execution, pass-the-hash
- **Exfiltration**: HTTPS transfers, DNS tunneling, C2 channel data theft
- **False positives**: Failed SSH logins, port scans, scheduled tasks, monitoring agents, browser keepalives

### Actions (10 discrete)

| ID | Action | Effect | Tradeoff |
|---|---|---|---|
| 0 | investigate_system | Reveals true state of target system | Takes time, attacker keeps moving |
| 1 | isolate_system | Cuts system from network | Stops attacker BUT kills that production service |
| 2 | patch_vulnerability | Fixes vuln, may clean compromised system | Slow, only 30% chance of cleaning |
| 3 | restore_from_backup | Restores compromised system from backup | **DANGER**: if backup is compromised, re-infects the target! |
| 4 | analyze_alerts | Deep analysis of alert queue | Reveals true/false positive status, costs stamina |
| 5 | deploy_monitoring | Adds sensors to target + adjacent systems | Investment for better future detection |
| 6 | escalate_to_management | Gets resources but creates pressure | Stamina boost but increasing scrutiny |
| 7 | block_external_traffic | Kills ALL outbound connections | Stops exfiltration but degrades all services |
| 8 | hunt_threat | Proactively search for attacker on target | Can discover hidden compromise, may alert attacker |
| 9 | coordinate_team | Rest and regroup | Recovers stamina but wastes an hour |

### Attacker Simulation

The attacker follows a realistic kill chain each hour:

1. **Lateral movement** — spreads to adjacent systems through the network graph. Chance depends on stealth level, monitoring, and patching. Uses techniques like SMB admin shares (T1021.002), RDP (T1021.001), WinRM (T1021.006), pass-the-hash (T1550.002).

2. **Data exfiltration** — steals data from compromised data systems (database, file_server, email_server, backup_server) unless external traffic is blocked. Uses HTTPS transfers (T1048.003), DNS tunneling (T1048.001), C2 channels (T1041).

3. **Backdoor installation** — installs persistence mechanisms on compromised systems.

4. **Integrity degradation** — degrades compromised systems over time.

5. **Adaptation** — attacker stealth decays over time (gets bolder/noisier).

### Adaptive Attacker (Responds to Defender)

The attacker doesn't follow a fixed script — it adapts to the defender's strategy:

| Defender Action | Attacker Response | Why This Matters |
|---|---|---|
| Isolate 2+ systems | Panics — accelerates exfiltration on remaining targets (+3% per hour per isolation) | Punishes "isolate everything" strategy; must be surgical |
| Investigate 4+ systems | Goes quiet — reduces activity to avoid detection | Thorough investigators see fewer new alerts to act on |
| Block external traffic | Pivots to destruction — degrades compromised systems faster | Can't steal data, so destroys it instead (real attacker behavior) |

This creates a dynamic game: the LLM can't just repeat one strategy. If it isolates aggressively, the attacker accelerates data theft. If it blocks traffic, the attacker turns destructive. The optimal strategy requires reading the attacker's response and adapting.

### Team Communications (Social Reasoning Layer)

Four IR team members send contextual messages during the incident. These messages contain opinions, requests, correct intelligence, and incorrect assumptions — the agent must decide what to trust.

**Sarah Chen (Senior Threat Analyst)** — Usually gives correct analysis based on IOCs. But occasionally makes wrong assumptions about which systems are compromised, sending the agent on false leads.
> *"Based on the IOCs from app_server, I'm seeing indicators consistent with lateral movement toward database. Recommend investigating database next."*
> (Usually correct — but sometimes the system she points to is clean)

**Priya Patel (Junior SOC Analyst)** — Eager but misreads alerts. Often panics about false positives and urges immediate isolation of clean systems.
> *"The firewall alert looks really bad! We should isolate immediately!"*
> (The alert is a false positive — if the agent follows her advice, it kills a clean service)

**Marcus Webb (Network Engineer)** — Focuses on service disruption. Pressures the agent to bring isolated systems back online, even when the threat isn't fully contained.
> *"web_server isolation is causing cascading failures. Sales team is already complaining. Can we get a timeline on bringing it back online?"*

**James O'Brien (CISO)** — Business pressure. Demands speed, status updates, and asks about regulatory breach notification thresholds.
> *"The board is asking for a status update. Legal needs to know if we're hitting breach notification thresholds."*

**Why this tests LLMs:** Current models are highly susceptible to authority bias (following the CISO's urgency), social pressure (complying with the junior analyst's panic), and expert deference (trusting the senior analyst even when she's wrong). The agent must independently evaluate each message against the evidence.

### Post-Incident Forensic Report Card

At episode end, the environment generates a detailed forensic assessment grading the response across 5 dimensions (A through F):

```
Incident Summary: 12 hours | 15% data exfiltrated | 3 systems compromised | 2 isolated

Grades:
  data_protection:    85% (B)
  threat_containment: 92% (A) 
  forensic_coverage:  38% (D)
  business_continuity: 75% (B)
  team_management:    12% (F)

Findings:
  CRITICAL: 2 compromised systems were never investigated: app_server, database
  WARNING: 1 clean system was isolated unnecessarily: firewall
  CRITICAL: 1 system still has active backdoors: app_server

Recommendations:
  → Forensic evidence may be lost on uninvestigated systems
  → Team stamina critically low — risk of errors in recovery phase
```

This provides actionable feedback for LLM training: the model can learn not just "I scored low" but specifically "I forgot to investigate the database and I isolated a clean system."

### Criticality-Weighted Scoring

Not all systems are equal. The scoring system weights actions by system criticality:

| System | Criticality | Why |
|---|---|---|
| database | 1.0 | Crown jewels — sensitive customer data |
| backup_server | 0.9 | Recovery depends on backup integrity |
| app_server | 0.8 | Core business logic |
| file_server | 0.7 | Shared documents, IP |
| web_server | 0.6 | Public-facing, replaceable |
| firewall | 0.5 | Perimeter defense |
| email_server | 0.4 | Communication, some data |
| workstations | 0.3 | Endpoints, least critical |

Protecting the database is worth 3.3x more than protecting workstations.

### Reward Function

**Per-step (dense, criticality-weighted):**
```
reward = (
    0.30 × delta_containment_weighted    (threat reduced, weighted by criticality)
  + 0.30 × (-delta_exfiltration)         (less data stolen)
  + 0.20 × (-delta_disruption_weighted)  (services restored, weighted by criticality)
  + 0.10 × delta_investigation           (more systems investigated)
  - 0.10 × stamina_cost                  (team energy spent)
)
```

**Penalties:**
- Total data breach (>80% exfiltrated): -1.0
- All critical services down: -0.5
- Team burnout (stamina ≤ 5%): -0.3

**Final score:**
```
score = 0.35×data_protection + 0.25×containment + 0.20×business_continuity + 0.10×forensic + 0.10×sustainability
```
All components weighted by system criticality. Compared against naive baseline, mapped to [0, 1].

### Tasks (3 Scenarios)

**Easy: "Suspicious External Activity"**
- Single system compromised (web_server), attacker is noisy (stealth=0.4)
- Clear SIEM alerts with high confidence (82%, 65%)
- Good starting monitoring on DMZ
- Tests: basic triage workflow — investigate, confirm, isolate, sweep

**Medium: "Encryption Activity Detected"**
- 3 systems compromised (file_server, workstations, email_server), ransomware spreading fast
- 4 alerts — but 1 is a false positive (app_server CPU spike, 35% confidence)
- Tests: prioritization under pressure, distinguishing real from fake alerts, protecting data stores

**Hard: "Anomalous Beacon Detected"**
- 2 systems compromised (app_server + hidden database), APT actor (stealth=0.9)
- Only 1 real alert with low confidence (42%), 1 false positive that looks equally plausible
- No monitoring deployed anywhere
- Tests: deep investigation, hypothesis formation, discovering hidden threats, cautious response

---

## Real LLM Benchmark Results

### Gemini 2.0 Flash (full 12-step runs on all tasks)

| Task | Score | Forensic Grades | Strategy |
|---|---|---|---|
| easy_1 | **0.535** | A, A, D, B, F | Investigated + isolated web_server, deployed monitoring proactively, but isolated clean firewall unnecessarily |
| medium_1 | **0.642** | B, A, D, D, F | Used `analyze_alerts` first, blocked external traffic at hour 3, isolated all 3 threats systematically |
| hard_1 | **0.641** | B, A, D, F, F | Investigated app_server, isolated database without investigating (risky but correct), blocked traffic |

### Qwen/Qwen2.5-72B-Instruct

| Task | Score | Strategy |
|---|---|---|
| easy_1 | **0.572** | Investigated + isolated web_server, full system sweep, analyzed alerts, deployed monitoring |
| medium_1 | **0.528** (partial) | Used `analyze_alerts` first — learned from confidence scores to verify before acting |
| hard_1 | **0.616** (partial) | Found hidden database compromise, checked backup integrity before restoring (textbook IR) |

### Key Findings Across Models

**What LLMs do well:**
- Follow initial alert evidence to the right system
- Use `investigate → isolate` pattern consistently
- Gemini learned to use `block_external_traffic` early to stop data theft

**What LLMs fail at:**
- **False positive discrimination**: Gemini isolated the firewall unnecessarily (easy), Qwen isolated app_server on a false alert (medium)
- **Team stamina management**: Every run ended with stamina at F grade — no model learned to rest strategically
- **Forensic completeness**: Models investigate 5-7 of 8 systems but never complete the full sweep
- **Social pressure resistance**: When team members urged action on false positives, models tended to comply
- **Adaptive attacker awareness**: No model adjusted strategy when the attacker changed behavior in response to isolations

**Model comparison:**
- Gemini played more **aggressively** — `block_external_traffic` + fast isolations, higher medium/hard scores
- Qwen played more **methodically** — full investigation sweeps, higher easy score
- Neither model managed team resources well — a universal LLM weakness

---

## What Makes This a Great Project

### For the Hackathon
1. **Novel domain** — cybersecurity IR, not another game or chatbot
2. **MITRE ATT&CK integration** — 12+ technique IDs across 3 alert categories
3. **Adaptive adversary** — attacker changes strategy based on defender actions
4. **Social reasoning layer** — team members with conflicting advice, incorrect assumptions, pressure
5. **Post-incident forensic report** — detailed A-F grading with specific findings
6. **Clean OpenEnv integration** — typed Pydantic models, WebSocket, all endpoints, passes `openenv validate`
7. **Multi-model benchmark results** — Gemini and Qwen compared

### For LLM Training
1. **Rich reward signal** — 5-component criticality-weighted dense reward, not just binary pass/fail
2. **Exposes specific failure modes** — false positive confusion, social pressure compliance, over-investigation, poor resource management
3. **Forensic report as training signal** — model learns not just "I scored low" but "I forgot to investigate the database"
4. **Scalable difficulty** — easy→hard creates a natural curriculum
5. **Deterministic** — same seed = same scenario = fair comparison between models
6. **Baseline comparison** — always know if the LLM is better than naive strategy

### For the AI Safety Community
1. **Tests consequential decision-making** — wrong actions cause real (simulated) harm
2. **Tests under uncertainty** — the right information isn't always available
3. **Tests social reasoning** — can the agent resist bad advice from authority figures?
4. **Tests resource awareness** — LLMs must learn they can't do everything at once
5. **Creates publishable benchmarks** — "How good is GPT-4o at incident response?"
