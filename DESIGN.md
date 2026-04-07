# Bastion: Cybersecurity Incident Response Environment

## Why This Project Exists

### The Problem with Current LLM Evaluation

Most LLM benchmarks test **knowledge recall** (trivia, coding syntax, math formulas). But real-world intelligence requires something harder: **making sequential decisions under uncertainty where early mistakes compound and information is incomplete**.

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

4. **Cascading consequences** — if you don't isolate a compromised database server, the attacker pivots from it to the backup server. If you isolate the wrong server, production goes down for nothing.

5. **No single correct answer** — there are better and worse trajectories, but the optimal strategy depends on what the attacker is doing, which you can only partially observe.

---

## How This Trains LLMs (The RL Pipeline)

### Step 1: Environment as Gym

```
┌──────────────┐     observation (JSON)      ┌──────────────┐
│              │ ───────────────────────────► │              │
│  Bastion   │                              │   LLM Agent  │
│  (this env)  │ ◄─────────────────────────── │  (policy π)  │
│              │     action (0-9)              │              │
└──────────────┘                              └──────────────┘
        │                                            │
        │  reward signal                             │
        └────────────────────────────────────────────┘
```

The LLM is the **policy** (π). It sees an observation and outputs an action. The environment returns a reward. Over many episodes, the LLM generates trajectories:

```
Episode 1: obs₀ → a₃ → r₁, obs₁ → a₇ → r₂, ... → final_score = 0.3  (bad)
Episode 2: obs₀ → a₁ → r₁, obs₁ → a₅ → r₂, ... → final_score = 0.8  (good)
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
- The LLM learns: "when I see high network_compromised + low investigation_progress, I should investigate before isolating"

**For Eval / Benchmarking:**
- Run different LLMs through identical scenarios (deterministic seeds)
- Compare their `comparison_score` against the baseline
- Publish results: "GPT-4o scores 0.72, Llama-3-70B scores 0.58, Claude scores 0.81"

### Step 3: What the LLM Actually Learns

The environment is designed so that optimal play requires:

| Skill | How It's Tested | Why LLMs Currently Fail |
|---|---|---|
| **Hypothesis formation** | Must interpret alerts + logs to form attack theory | LLMs take alerts at face value, don't cross-reference |
| **Information gathering vs action** | Must decide when to investigate vs when to act | LLMs either investigate forever or act too quickly |
| **Risk assessment** | Must weigh "cost of being wrong" for each action | LLMs don't model downside risk well |
| **Prioritization** | Multiple systems under attack, limited actions per turn | LLMs try to do everything at once or focus on the wrong thing |
| **Adaptive strategy** | Attack evolves — initial plan must be revised | LLMs anchor on their first hypothesis |
| **Resource management** | Team stamina depletes, tools have cooldowns | LLMs ignore resource constraints |

---

## Environment Design

### The Scenario

You are the **Incident Commander** at a mid-size tech company. Your network has been breached. An Advanced Persistent Threat (APT) actor is inside your network, moving laterally, exfiltrating data, and escalating privileges.

You have a 12-step window (each step = 1 hour of incident response) to contain the breach, minimize data loss, and restore operations.

### State (What's Really Happening)

```
Network: 8 systems (web_server, app_server, database, file_server,
                     email_server, workstations, backup_server, firewall)

Each system has:
  - compromised: bool        (is the attacker on this system?)
  - isolated: bool           (have we cut it off from the network?)
  - investigated: bool       (have we forensically analyzed it?)
  - integrity: float (0-1)   (how intact is the data/service?)
  - criticality: float       (how important is this system? database > workstations)

Global state:
  - attacker_progress: float (0-1)    how much of their objective they've achieved
  - attacker_stealth: float (0-1)     how hidden the attacker remains
  - data_exfiltrated: float (0-1)     how much sensitive data has been stolen
  - services_disrupted: int           how many production services are down
  - team_stamina: float (0-1)         your IR team gets tired (affects effectiveness)
  - alert_queue: list[Alert]          incoming security alerts (some are noise)
  - hour: int (0-12)                  time step
```

### Observation (What the Agent Sees — NOISY)

The agent does NOT see the true state. Instead:
- **Alerts** are noisy — some are false positives, some real attacks are missed
- **Compromise status** is unknown until a system is investigated
- **Data exfiltration** is estimated with delay and noise
- **Attacker progress** is invisible — you only see its effects
- `analyze_alerts` reveals more accurate information for one step

### Actions (10 discrete)

| ID | Action | Effect | Tradeoff |
|---|---|---|---|
| 0 | investigate_system | Reveals true state of a system | Takes time, attacker keeps moving |
| 1 | isolate_system | Cuts system from network | Stops attacker BUT kills that service |
| 2 | patch_vulnerability | Fixes known vuln on a system | Slow, only helps if vuln is relevant |
| 3 | restore_from_backup | Restores a compromised system | Only works if backup isn't compromised too |
| 4 | analyze_alerts | Deep analysis of alert queue | Reveals true positives, costs team stamina |
| 5 | deploy_monitoring | Adds sensors to detect attacker movement | Future alerts more accurate |
| 6 | escalate_to_management | Buys resources but creates pressure | Gets help but adds time pressure / scrutiny |
| 7 | block_external_traffic | Kills all outbound connections | Stops exfiltration but disrupts everything |
| 8 | hunt_threat | Proactively search for attacker indicators | Can find attacker but might alert them |
| 9 | coordinate_team | Rest and reorganize the IR team | Recovers stamina but wastes an hour |

### Attacker Simulation (the "adversary")

The attacker follows a realistic kill chain:
1. **Initial access** → already happened (pre-scenario)
2. **Lateral movement** → spreads to adjacent systems each hour
3. **Privilege escalation** → gets deeper access over time
4. **Data exfiltration** → steals data from compromised databases/file servers
5. **Persistence** → installs backdoors that survive reboots

The attacker:
- Moves faster when undetected (stealth is high)
- Slows down when the defender investigates (attacker gets cautious)
- Can pivot to backup systems if primary targets are isolated
- Has a 12-hour objective window

### Reward Function

**Per-step (dense):**
```
reward = (
    +0.3 × delta_containment        (attacker's spread reduced)
    +0.3 × (-delta_exfiltration)     (less data stolen)
    +0.2 × (-delta_disruption)       (services restored)
    +0.1 × delta_investigation       (more systems investigated)
    -0.1 × action_cost               (team stamina spent)
)
```

**Penalties:**
- Total data exfiltration > 80%: -1.0 (catastrophic breach)
- All critical services down: -0.5
- Team burnout (stamina = 0): -0.3

**Final score:**
```
score = (
    0.35 × (1 - data_exfiltrated)          (data protection)
    + 0.25 × (1 - attacker_progress)       (containment)
    + 0.20 × (services_intact / total)     (business continuity)
    + 0.10 × (systems_investigated / total) (forensic completeness)
    + 0.10 × team_stamina                   (sustainable response)
)
```

### Tasks (3 Scenarios)

**Easy: "Script Kiddie"**
- Amateur attacker, slow lateral movement
- Only 2 systems initially compromised
- Clear, accurate alerts
- Goal: contain and investigate

**Medium: "Ransomware Outbreak"**
- Fast-spreading malware hitting multiple systems
- 4 systems compromised, spreading quickly
- Many alerts (some false positives)
- Must prioritize: stop the spread or save data?

**Hard: "APT — Advanced Persistent Threat"**
- Sophisticated nation-state actor
- Only 1 system compromised but deep access
- Mostly stealthy — few alerts, many false positives
- Attacker actively evades detection
- Must investigate carefully before acting

---

## What Makes This a Great Project

### For the Hackathon
1. **Novel domain** — nobody else is building this
2. **Technically credible** — Meta engineers deal with security daily
3. **Tests genuine LLM weaknesses** — not just math optimization
4. **Clean OpenEnv integration** — proper typed models, WebSocket, all endpoints
5. **Research-relevant** — automated incident response is a real research area

### For LLM Training
1. **Rich reward signal** — dense per-step feedback, not just binary pass/fail
2. **Exposes specific failure modes** — anchoring, recency bias, poor prioritization
3. **Scalable difficulty** — easy→hard tasks create a curriculum
4. **Deterministic** — same seed = same scenario = fair comparison
5. **Baseline comparison** — always know if the LLM is better than naive strategy

### For the AI Safety Community
1. **Tests consequential decision-making** — wrong actions cause real (simulated) harm
2. **Tests under uncertainty** — the right information isn't always available
3. **Tests resource awareness** — LLMs must learn they can't do everything at once
4. **Creates publishable benchmarks** — "How good is GPT-4o at incident response?"
