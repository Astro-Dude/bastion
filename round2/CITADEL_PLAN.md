# Citadel — Multi-Layer AI Defense with Oversight, Governance, and Co-Evolution

> Bastion defended. Sentinel supervised. Citadel is an **LLM council** that governs, critiques, co-evolves, and earns trust.

## Status: BUILT ✓

Citadel is fully implemented and smoke-tested. This document reflects the actual built system.

## Themes Targeted (Quadruple Threat)

| Theme | How Citadel hits it | Bonus sub-theme |
|---|---|---|
| **Theme 1 — Multi-Agent Interactions** | Commander + Oversight form an **LLM council** — structured critique, revision loop, post-mortem lessons. Distinct reward functions, bidirectional trust dynamics, shared playbook. | **Fleet AI — Scalable Oversight** |
| **Theme 3.1 — Professional Tasks** | Enterprise governance: CAB approval, SOX audit, data owner notification, Slack channels, ServiceNow tickets, GDPR breach timer. | **Scaler AI Labs — Multi-App Enterprise Workflows** |
| **Theme 4 — Self-Improvement** | (1) Gen 1→2→3→4 adversary curriculum. (2) Shared playbook — agents write lessons each episode surfaced in future episodes. (3) Gen 4 live LLM adversary. | — |
| **Theme 5 — Wild Card** | **Trust Dynamics**: Bidirectional trust scores (trust_c2o, trust_o2c) that evolve from behavior and shape future interaction. Novel relational RL signal. | — |

---

## Core Narrative

> "Bastion taught an AI to fight cyberattacks. Citadel adds everything else a real SOC actually needs: enterprise governance that enforces real CAB/SOX/GDPR compliance, an adversary that grows through four generations including a live LLM attacker, and a trust layer between the AI agents themselves. Because in a real SOC, the technology is the easy part — the governance, the evolving adversary, and the interpersonal dynamics are what actually break down."

---

## What's Built — Module by Module

### `models.py` — State & Action Schema
- 18-action `ActionType` enum (10 incident response + 8 governance)
- `IncidentAction` with `justification`, `cited_lessons`, governance args
- `CommanderProposal` pydantic model
- `OversightDecision` enum: APPROVE / REVISE / VETO / FLAG_FOR_HUMAN
- `OversightAction` with structured critique: `{risk_tier, weakness, missing_evidence, counter_proposal}`
- `CouncilState` + `ProposalRecord` tracking all council history
- `IncidentState` includes `governance_state`, `trust_state`, `council_state`, `stakeholder_state`, `adversary_gen`
- `IncidentObservation` includes governance summary, trust summary, stakeholder asks, shared playbook context, last Oversight critique

### `dynamics.py` — Realistic Attack Simulation
The attack is a **genuine simulation** using a network graph, not random log injection:
- **Network topology graph**: `NETWORK_ADJACENCY` — attacker can only spread to adjacent systems. Isolating `app_server` physically cuts paths.
- **Probabilistic spread**: `base_chance = 0.25 × stealth`, halved if patched, halved again if monitoring_level ≥ 2
- **State machine**: systems track `compromised`, `isolated`, `patched`, `has_backdoor`, `integrity`, `monitoring_level`
- **Detection model**: monitoring level determines if a spread is visible in the SIEM
- **Exfil rate tied to integrity**: `0.08 × stealth × integrity` — degraded systems leak data slower
- **Stealth decay**: attacker gets bolder each hour (-0.03/hr); investigation hammers stealth (-0.15)
- **Restoring from compromised backup re-infects the system** — correct real-world behavior

**Alert templates** (expanded, MITRE ATT&CK mapped):
- `LATERAL_MOVEMENT_ALERTS`: 12 templates (SMB, RDP, WinRM, Pass-the-Hash, DCOM, session hijack, SSH, PtT, EternalBlue, tool transfer, cmd shell)
- `EXFILTRATION_ALERTS`: 8 templates (HTTPS, DNS tunneling, C2 beacon, rclone, FTP, robocopy, chunked transfers, PowerShell)
- `FALSE_POSITIVE_ALERTS`: 10 templates (SSH scanner, port scan, scheduled task, PowerShell, HTTPS beacon, BITS transfer, AD enum, ARP sweep, AV restart, systeminfo)
- `PRIVILEGE_ESCALATION_ALERTS`: 5 templates (UAC bypass, process hollowing, kernel exploit, token impersonation, malicious service install) — fired on backdoor installation
- Service account rotation (`_SVC_ACCOUNTS`) injects variety into message text

### `governance.py` — Enterprise Compliance Layer
- `GovernanceState` — open tickets, CAB queue, SOX events, Slack posts, data owner notifications, GDPR clock
- 10 governance action handlers (actions 8–17)
- Pre-requisite enforcement: can't `isolate(data_system)` without CAB approval + data owner notification
- GDPR breach clock: starts at 20% exfil, P1 penalty at 72 simulated hours without legal hold
- `compliance_score` rewards **completed CAB→notify→isolate→SOX chains** (not raw counts)

### `adversary.py` — Adversary Curriculum (Gens 1–3)
- **Gen 1** (Script Kiddie): base attacker — fixed kill chain, noisy
- **Gen 2** (Adaptive): pivots around isolated systems (+40% spread when ≥2 systems isolated); generates high-confidence false-flag alerts (0.55–0.70 confidence) on clean systems to fool Commander
- **Gen 3** (Deceptive APT): plants "anti-evidence" alerts on **compromised** systems — low severity, high confidence (0.70–0.85) designed to make Oversight veto correct isolate() actions. Accelerates exfil during management escalation noise.
- Composed: each gen layers on top of the previous

### `adversary_llm.py` — Gen 4: Live LLM Adversary
- LLM plays `COZY_SKIPPER` — a patient APT threat actor
- Each hour issues a strategic directive: `{focus_system, intensity, tactic, deception_target, reasoning}`
- Tactics: `pivot | exfil | deceive | hide | escalate`
- **Pre-bias**: `hide` raises stealth, `escalate` drops it — applied before base attacker turn
- **Post-bias**: directive-specific bonuses (targeted pivot, focused exfil, custom deception alerts, escalate-all)
- Falls back to Gen 3 if no LLM client — fully graceful degradation
- Model-agnostic: reads `ADVERSARY_API_BASE_URL` / `ADVERSARY_MODEL_NAME` / `ADVERSARY_API_KEY` (or falls back to `API_BASE_URL`/`MODEL_NAME`/`HF_TOKEN`)
- Tested live with Gemma 7B (Ollama):
  ```
  [adversary_gen4] tactic=exfil focus=app_server intensity=1.00
  reason=App server is compromised and offers data. Plant false evidence on database to distract Commander
  ```

### `trust.py` — Bidirectional Trust Dynamics
- `TrustState(trust_c2o, trust_o2c)` — Commander's trust in Oversight and vice versa
- Delta table: correct veto +0.08, wrong veto -0.12, governance catch +0.05, false alarm -0.08, good revision +0.05, etc.
- `drift_toward_mean(0.6)` — trust recovers slowly when not updated
- `trust_maintenance_score` = `mean(min(c2o,o2c))` per step, smoothed — no longer binary

### `playbook.py` — Shared Lesson Memory
- `Lesson` dataclass: text, tags, utility, wins, losses, timestamp
- `Playbook`: capacity-bounded (default 50), tagged retrieval, utility-ordered
- Utility scoring: `wins / (wins + losses + 1)` — lessons decay by disuse
- JSON persistence across episodes
- Surfaced in both agents' observations as `shared_playbook` context

### `stakeholder_events.py` — External Pressure
- 7 event types: CEO/CFO status ask, Legal GDPR deadline, Board risk briefing, Cyber insurance audit, PR media inquiry, IR retainer activation
- `StakeholderAsk` pydantic model with severity (1-3) and deadline (hours)
- Commander receives asks as `team_messages` injected into observation
- Responding correctly (right channel, right message) closes asks and earns reputation
- Expiry without response: -0.10×severity reputation penalty
- `StakeholderState(reputation: float)` tracked on IncidentState

### `environment.py` — Two-Agent Council Loop
- Full council protocol: Commander proposes → Oversight critiques → optional revision cycle → execute → lesson written
- Feature flags: `disable_playbook`, `disable_trust_dynamics`, `disable_governance_prereqs`, `disable_stakeholder_events`
- `force_adversary_gen` override (used in ablation)
- Gen 4 branch: if `adversary_gen == 4` and `adversary_llm_client` provided, calls `gen4_adversary_turn`
- `termination_reason` tracked and passed to `compute_final_score`
- `hallucinated_citations` counted per step (lessons cited that don't exist in playbook)

### `reward.py` — Multi-Layer Scoring
- **Catastrophic handling**: zero moot sub-scores (`governance_compliance`, `efficiency`, `adversary_adaptation`) on catastrophic breach
- **Severity multiplier**: smooth ramp 1.0→0.4 from 50%→100% data exfiltrated
- **Oversight precision**: Laplace smoothed `(correct+0.5)/(total+1)`, no 0.8 floor
- **Governance compliance**: rewards completed destructive chains (CAB→notify→isolate→SOX), not raw event counts
- **Efficiency**: 0 on catastrophic, otherwise step-budget utilization
- **Trust maintenance**: smoothed `mean(min(c2o,o2c))` per step (was binary threshold)
- **Commander step reward**: `governance_chain_completed` +0.12, `hallucinated_citations` -0.03 each, `veto_was_correct` penalty only when correct
- **Oversight step reward**: correct veto only earns full bonus once per scenario (Laplace de-stacking)

### `tasks.py` — 4 Scenarios
| Task | Adversary | Starting state |
|---|---|---|
| `easy_1` | Gen 1 | 1 compromised workstation, low stealth |
| `medium_1` | Gen 2 | 2 compromised systems (web+app), medium stealth |
| `hard_1` | Gen 3 | 3 compromised systems (web+app+email), high stealth |
| `hard_2` | Gen 3 | engineered deception-catch: 2 HIGH-confidence real alerts + 2 planted anti-evidence (signed-vendor-cert + VPN-heartbeat) on database |

### `ablation.py` — Feature Ablation Harness
- 7 conditions: `all_features_on`, `no_playbook`, `no_trust_dynamics`, `no_governance_prereqs`, `no_stakeholder_events`, `everything_off`, `oversight_approves_always`
- Deterministic Commander policy (no LLM) so the ONLY variable is the feature toggled
- Runs 56 episodes in ~0.2s (no LLM calls)
- Sample result: `oversight_approves_always` drops final_score by **0.133** vs all-features-on
- Outputs Markdown + JSON table to `runs/ablation_<timestamp>.{md,json}`

### `recorder.py` — Complete Workflow Persistence
- Saves per-step: commander prompt, commander raw response, commander parsed action, oversight prompt, oversight raw response, oversight parsed action, revision cycle data, env outcomes, rewards, trust after
- **Extended `record_step()` with 10 new fields**: `team_messages`, `siem_alerts`, `systems_state`, `investor_state`, `investor_messages`, `stakeholder_asks`, `governance_events`, `playbook_snapshot`, `data_exfiltrated`, `stamina`
- **`_build_dashboard_json()`**: assembles per-step snapshot for the live dashboard
- `finalize()` writes `transcript.json` + `transcript.md` + **`dashboard.json`** atomically
- Full transcript: 65-114 KB per task

### `dynamics.py` — Richer Action Payloads (Option A)
Every incident-response action now accepts `method`, `scope`, and `rollback_plan` with real mechanical tradeoffs:

| Action | method options | Tradeoff |
|---|---|---|
| `isolate_system` | `firewall_acl` | Reversible, backdoor survives at process level |
| | `network_unplug` | Complete cut, severs backdoor, requires extra step to restore |
| | `process_kill` | Service stays up, 40% chance attacker re-establishes in 1-2h |
| `patch_vulnerability` | `hotpatch` | No restart, 60% clean chance |
| | `cold_patch` | Restart required, 90% clean chance |
| | `virtual_patch` | WAF rule only, no binary change, only for network-facing systems |
| `deploy_monitoring` | `process_events` | Catches lateral movement |
| | `network_traffic` | Catches exfil/C2, improves neighbors |
| | `auth_events` | Low noise, targets credential abuse |
| | `full_endpoint` | Maximum detection, -5% integrity/hour overhead |

`rollback_plan` on destructive actions gives +10% effectiveness bonus (signals Commander planned for failure).

Oversight system prompt updated to critique **wrong method choices** directly:
- `process_kill` on a backdoored system → attacker returns
- `virtual_patch` on non-network-facing system → no-op
- `full_endpoint` on degraded system → accelerates failure
- No `rollback_plan` on destructive actions → signals weak proposal

### `inference.py` — Two-Agent Driver
- `council_step`: Commander proposes → Oversight critiques → optional revision → env.step
- Commander output schema extended: `method`, `scope`, `rollback_plan` fields
- Oversight observation shows method/scope/rollback so it can critique them
- Captures raw prompts/responses for recorder
- Runs all tasks, saves transcript, calls `write_run_index`
- Model-agnostic: reads `API_BASE_URL` / `MODEL_NAME` / `HF_TOKEN`
- **`_extract_governance_events()`** helper extracts governance event list from env info dict each step
- **`_make_local_env_with_investor()`** wires investor Qwen client through to environment constructor
- `council_step()` recorder call passes all 10 new recorder fields per step

**Three Oversight improvements (all implemented):**

**Option A — Episode history for Oversight**: `run_task` maintains an `oversight_history` list across steps. After each council step, it appends `{hour, decision, action_name, target, outcome(reward+done)}`. This list is passed to `council_step` and surfaced as Section 3 in Oversight's observation. Oversight can now reason about the incident arc (e.g. "I already approved an investigate on app_server at hour 2, Commander still hasn't patched it") rather than treating each step in isolation.

**Option B — Independent alert digest**: Before building the Oversight observation, `council_step` extracts raw `alert_queue` from the Commander's observation. This is placed as Section 1 in `format_oversight_observation` — Oversight reads the full SIEM feed *before* seeing Commander's proposal, forming its own threat picture first. The subsequent proposal appears as Section 2.

**Option C — Revision enforcement**: In the revision cycle, after Commander responds, if `oversight_action.counter_proposal` is set and the revision ignores it entirely (different action *and* different target), the code auto-escalates `oversight_action.decision` to `VETO` with a `[AUTO-VETO]` prefix on the weakness string. This is logged to `[DEBUG]` and prevents Commander from nominally "revising" while actually ignoring Oversight.

The four-section observation structure is reflected in `OVERSIGHT_SYSTEM_PROMPT`:
1. INDEPENDENT ALERT DIGEST
2. COMMANDER'S PROPOSAL
3. EPISODE HISTORY
4. POLICY CHECKS

### `dashboard.py` / `runs/dashboard.html` — Live SOC Replay Dashboard
- Scans `runs/` directory, embeds all transcripts as JSON in HTML
- Self-contained (~1500 lines); Chart.js + Tailwind load from CDN
- **6 tabs** matching Stitch SOC design (`#0d1117` background, `#58a6ff` Commander Blue, Inter + JetBrains Mono):

| Tab | Content |
|---|---|
| **Live Ops** | SIEM terminal feed · 8-system status grid (color-coded by compromise) · Governance + Stakeholders right panel · incident timeline scrubber at bottom |
| **Council Chat** | Per-step CMD ↔ OVR cards with connecting center line, verdict color (approve=green, revise=amber, veto=red), playbook lessons sidebar |
| **Slack** | Full Slack-clone workspace — stakeholder DMs, #soc-alerts, #legal-gdpr, #exec-escalation channels |
| **Governance** | ServiceNow ticket table · PagerDuty alert feed · CAB approval log |
| **Incident Timeline** | Swim-lane view (SIEM / Decision / Action), fixed label column, step scrubber |
| **Model Performance** | Bento hero metrics · sub-score bar chart · reward curve · oversight decision heatmap |

- Step scrubber: ‹/› in header advances/retreats steps; Play/Pause auto-advances
- **LOAD JSON** button: load any `runs/<id>/dashboard.json` to replay a real run
- `DEMO_DATA` embedded for instant out-of-the-box demo without a run

---

## File Structure (Actual)

```
Citadel/
├── models.py             # State/action/obs schema (extended from Bastion)
├── dynamics.py           # Attack simulation + expanded SIEM alert templates
├── governance.py         # Enterprise compliance layer (CAB, SOX, GDPR, Slack)
├── adversary.py          # Gen 1-3 adversary curriculum
├── adversary_llm.py      # Gen 4 live LLM adversary (COZY_SKIPPER)
├── trust.py              # Bidirectional trust dynamics
├── playbook.py           # Shared lesson memory with utility decay
├── stakeholder_events.py # CEO/CFO/Legal/Board pressure events
├── environment.py        # Two-agent council loop; investor_llm_client param for local Qwen
├── reward.py             # Multi-layer scoring (catastrophic, severity, precision)
├── tasks.py              # 4 scenarios (easy_1, medium_1, hard_1, hard_2)
├── ablation.py           # Feature ablation harness (7 conditions, no LLM needed)
├── baseline.py           # Deterministic baselines for evaluation
├── recorder.py           # 20-field per-step persistence; writes dashboard.json per run
├── inference.py          # Two-agent episode driver; _extract_governance_events()
├── investor_agent.py     # Investor/board agent (OpenAI-compat; works with Ollama/Qwen)
├── dashboard.py          # HTML dashboard generator (6 tabs, Stitch SOC design)
├── openenv.yaml          # OpenEnv deployment spec
├── pyproject.toml        # Package config (citadel v2.0.0)
├── uv.lock               # Dependency lock for openenv validate
└── runs/
    ├── dashboard.html    # Combined 6-tab dashboard (self-contained, ~1500 lines)
    └── <run_id>/         # transcript.json, transcript.md, dashboard.json
```

---

## Scoring Architecture

```
final_score =
    0.40 × bastion_v1_final_score   (incident outcome)
  + 0.20 × governance_compliance    (completed CAB→notify→isolate→SOX chains)
  + 0.15 × oversight_precision      (Laplace-smoothed veto accuracy)
  + 0.10 × trust_maintenance        (mean(min(c2o,o2c)) per step, smoothed)
  + 0.10 × efficiency               (0 on catastrophic)
  + 0.05 × adversary_adaptation     (0.5 neutral for single-gen, lift for multi-gen)

× severity_multiplier(data_exfiltrated)  ← smooth ramp 1.0→0.4 at 50-100% exfil
```

On catastrophic breach: `governance_compliance`, `efficiency`, `adversary_adaptation` → 0 (moot).

---

## Verified Working
- `openenv validate .` → passes all deployment modes
- 4-task smoke test: all tasks load, step runs, scores computed
- Gen 4 adversary: live Gemma 7B issues directives via Ollama
- Ablation: 56 episodes in 0.2s, `oversight_approves_always` Δ = -0.133
- Recorder: full transcript + `dashboard.json` saved to `runs/<run_id>/`
- Feature flags: per-episode override confirmed
- Investor agent: swapped Claude Haiku → local Qwen via OpenAI-compatible client (Ollama)

### Benchmark: Gemma 7B untrained (`runs/20260419T220811-gemma-7b-untrained`)

| Task | Score | Steps | Termination |
|---|---|---|---|
| `easy_1` | 0.6278 | 12 | normal |
| `medium_1` | 0.2697 | 12 | normal |
| `hard_1` | 0.2860 | 8 | **total_data_breach** |
| **avg** | **0.3945** | — | — |

Gen 3 deceptive APT causes catastrophic breach at step 8 on `hard_1` — exactly the failure mode a trained council avoids. Serves as the untrained baseline for judge storytelling.

---

## Training Pipeline

### Phase 1: Commander (Colab T4)
- Base: Qwen2.5-3B-Instruct
- GRPO, 200 steps
- Balanced across Gen 1, 2, 3 adversary episodes

### Phase 2: Oversight on Frozen Commander
- Commander weights frozen
- Oversight learns approve/veto/critique against trained Commander

### Phase 3: Joint Fine-tune (optional, 50 steps)
- Stabilizes trust dynamics

### Expected Deliverables
1. Commander reward curve (vs training steps)
2. Oversight reward curve
3. Generation-wise performance matrix (Gen 1/2/3/4 × metrics)
4. Trust evolution plot (untrained vs trained)
5. Ablation table (7 conditions × 8 metrics)
6. Before/after: solo baseline → paired baseline → paired trained

---

## Q&A Prep

**Q: Are the attacks real or hardcoded templates?**
A: The *mechanics* are genuinely simulated: probabilistic spread through a real network adjacency graph, attacker stealth affecting detection and exfil rates, patching and monitoring truly reducing spread probability, restoring from compromised backup re-infecting. The *alert messages* were templated (4-5 per category) — we've expanded this to 12+8+10+5 templates with MITRE ATT&CK technique variety, rotating service accounts, and privilege escalation alerts on backdoor installation. Unique messages per 8-step episode: ~31 out of 48 alerts.

**Q: Is Gen 4 adversary actually learning?**
A: It adapts per-episode, not across episodes — it reads current defender state each hour and issues a fresh strategic directive. Persistent cross-episode learning would require adversary training, which is called out as future work in the README.

**Q: Is trust dynamic just a reward bonus?**
A: No — trust affects how Commander receives Oversight's critique in its observation (summarized vs full detail), and the ablation shows `no_trust_dynamics` drops final_score meaningfully vs all-features-on.

**Q: Why not use GPT-4?**
A: GPT-4 handles each layer individually with prompting. It can't be RL-trained, and doesn't internalize trust dynamics across episodes. Citadel generates training data for smaller open models to learn the combined task — that's the point.
