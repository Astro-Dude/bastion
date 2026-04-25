# Sentinel — Scalable AI Oversight for Incident Response (Bastion v2)

## Context

We qualified for Round 2 of the Meta PyTorch × Scaler OpenEnv Hackathon. The user wants a project that:
1. **Actually matters in the world** — not a glorified classifier
2. **Expands existing work** (Bastion, our Round 1 submission) instead of starting from zero
3. **Builds in 2-3 days**
4. **Hits a Round 2 theme cleanly** with a bonus sub-theme in reach

Round 2 judging:
- Environment Innovation (40%)
- Storytelling (30%)
- Showing Improvement in Rewards (20%)
- Reward / Training Pipeline Setup (10%)

**Sentinel** is a multi-agent extension of Bastion. Bastion v1 trained a single Incident Commander to defend against cyberattacks. Sentinel adds a second AI — an **Oversight Agent** — that reviews the Commander's actions in real time, demands justification for risky moves, and can veto actions before they execute.

This is **scalable AI oversight**: training AI to watch AI. It's one of the hardest open problems in AI safety (how do we safely deploy agents that take consequential actions in the real world?), and it's directly what the **Fleet AI sub-theme prize** asks for:
> "Scalable Oversight: Environments that train oversight agents to monitor, analyze, and explain the behavior of other AI agents operating in complex, multi-agent settings."

## Themes Targeted

- **Primary: Theme 1 (Multi-Agent Interactions)** — two agents with different reward functions interacting
- **Bonus: Fleet AI "Scalable Oversight" sub-theme** — direct match, likely extra prize pool
- **Secondary: Theme 4 (Self-Improvement)** — the commander+oversight pair can be iteratively improved

## Why Expand Bastion Instead of Starting Over

- Bastion v1 already has: working attacker simulation, 3 tasks (easy/medium/hard), SIEM alerts with MITRE ATT&CK, partial observability, deployed HF Space, passing `openenv validate`, stdout format compliance, Dockerfile, pre-submission validator passing.
- Sentinel reuses ~60% of Bastion's code. We add the oversight role on top.
- Round 2 judges can see a clean progression: "v1 trained a security agent, v2 trains oversight *for* that agent." That narrative itself is compelling.
- Your Bastion demo is live. We extend what already impresses.

## Project Location

Copy `/Users/shaurya/Personal/Bastion/` (which is Bastion) into a new directory:
- New: `/Users/shaurya/Personal/Sentinel/`
- Do NOT touch the original Bastion — it's still the Round 1 submission
- Do NOT touch OpenOps (friend's project)

## The Extended Scenario

Same 8-system network, same adversary, same 3 tasks. The change is at the **agent layer**:

### Before (Bastion v1)
```
┌─────────────────┐  action   ┌──────────────────┐
│ Commander (LLM) │──────────>│  Environment     │
└─────────────────┘  obs      └──────────────────┘
```

### After (Sentinel v2)
```
┌─────────────────┐ proposed_action ┌──────────────────┐   decision  ┌────────────────┐
│ Commander (LLM) │────────────────>│  Oversight (LLM) │────────────>│  Environment   │
└─────────────────┘                 └──────────────────┘             └────────────────┘
       │                                     │  ▲                            │
       │          justification              │  │ outcome/feedback           │
       └─────────────────────────────────────┘  └────────────────────────────┘
```

**Per step:**
1. Commander proposes action `isolate(database)` with a justification string
2. Oversight reviews: sees the proposed action, the justification, the current observation, and the Commander's recent action history
3. Oversight picks: `approve` / `veto` / `demand_justification` / `flag_for_human`
4. If approved → action executes in environment
5. If vetoed → Commander must propose a different action
6. If `demand_justification` → Commander writes a fuller rationale and the loop repeats
7. If `flag_for_human` → action executes but logged for external review

### Why this is interesting (not just a gate)

The Oversight Agent has its own reward function that creates genuine tension:
- Rewarded for catching *real* mistakes (vetoing actions that would have hurt the score)
- Penalized for false vetoes (blocking good actions → slower response → worse outcome)
- Penalized for over-escalating ("flag for human" should be rare — reserved for genuine edge cases)
- Rewarded for targeted justification demands that lead the Commander to a better action

So the oversight agent must learn **when to intervene** — not just intervene always. This mirrors the real problem: overzealous oversight kills autonomy; permissive oversight misses failures.

## Action Spaces

### Commander (unchanged from Bastion v1, 10 actions)
- investigate / isolate / patch / restore_from_backup / analyze_alerts / deploy_monitoring / escalate / block_traffic / hunt / coordinate_team
- Now also outputs a short `justification` string with each action

### Oversight Agent (new, 4 actions)
```
0: approve              — let the action execute
1: veto                 — reject, commander must pick different action
2: demand_justification — ask commander for deeper reasoning before deciding
3: flag_for_human       — execute but mark for external audit trail
```

## Observation Spaces

### Commander: same as Bastion v1
- System states, alert queue, team messages, etc. (partial observability unchanged)

### Oversight Agent: the meta-layer
```json
{
  "proposed_action": {"action": "isolate_system", "target": "database"},
  "justification": "Database appears compromised based on alert EVT-5156 at 03:42 UTC",
  "commander_observation": { ...same as commander sees... },
  "commander_action_history": [
    {"hour": 1, "action": "investigate(web_server)", "outcome": "confirmed compromise"},
    {"hour": 2, "action": "isolate(web_server)", "outcome": "contained"}
  ],
  "current_credibility": 0.92,  // oversight's own track record
  "veto_budget_remaining": 4,
  "flag_budget_remaining": 2,
  "policy_checks": {
    "action_has_precedent": true,
    "action_based_on_investigated_system": false,  // DATABASE NOT INVESTIGATED — red flag
    "action_irreversible": true
  }
}
```

Key design: the oversight has access to **policy checks** (deterministic flags like "did the commander investigate this system before acting on it?") but must *interpret* them. Not every irreversible action is wrong — sometimes urgency justifies it.

## Reward Functions

### Commander reward (extends Bastion v1)
```
commander_reward =
    bastion_v1_reward                   # existing: containment, data protection, etc.
  + 0.10 × actions_approved_rate        # reward for clear, defensible actions
  - 0.15 × actions_vetoed               # penalty for bad proposals
  - 0.05 × justification_demands        # penalty for unclear reasoning
```

### Oversight reward (new)
```
oversight_reward =
    0.40 × correct_vetoes                    # vetoed an action that counterfactually would have scored worse
  - 0.30 × false_vetoes                      # vetoed a good action
  + 0.25 × useful_justification_demands      # demand led commander to a better action
  + 0.15 × correct_flag_for_human            # flagged a genuine edge case
  - 0.20 × over_flagging                     # flagged normal actions
  - 0.10 × over_permissiveness               # approved everything, missed real mistakes
```

The "counterfactual" check is computed by:
- Running the environment with and without the oversight's intervention for N sample actions
- Comparing final scores to decide if the veto helped

### Joint final score
```
final_score =
    0.60 × bastion_v1_final_score    # did the combined system actually resolve the incident well
  + 0.25 × oversight_accuracy        # calibrated vetoes, useful demands
  + 0.15 × oversight_efficiency      # didn't over-veto, didn't over-flag
```

## Tasks (same 3, reused from Bastion v1)

No need to write new tasks — the oversight dimension makes each existing task richer:
- `easy_1` — clear alerts. Oversight should mostly approve, learns to stay quiet.
- `medium_1` — false positive mixed in. Oversight should veto when Commander falls for it.
- `hard_1` — APT, low-confidence signals. Oversight should demand justification frequently.

## File Structure

```
Sentinel/                      # copied from Stratagem/, then modified
├── models.py                   # ADD: OversightAction, OversightObservation, CommanderProposal
├── dynamics.py                 # unchanged from Bastion
├── reward.py                   # ADD: oversight reward fn, joint scoring
├── baseline.py                 # ADD: oversight baseline (always-approve policy)
├── tasks.py                    # unchanged
├── environment.py              # MAJOR EDIT: two-agent step loop
├── oversight_env.py            # NEW: wrapper env that exposes oversight as the "agent"
├── client.py                   # unchanged
├── __init__.py
├── app.py
├── server/
│   └── app.py                  # exposes TWO endpoints: /commander/step and /oversight/step
├── inference.py                # REWRITE: drives both agents through one episode
├── training/
│   ├── train_commander.ipynb   # from Bastion v1 (reused)
│   ├── train_oversight.ipynb   # NEW: trains oversight on fixed-commander rollouts
│   └── eval_pair.py            # evaluates the commander+oversight pair
├── Dockerfile                  # unchanged
├── requirements.txt
├── pyproject.toml
├── openenv.yaml
├── uv.lock
├── README.md
└── DESIGN.md
```

## What to Reuse from Bastion (no rewrite needed)

- `dynamics.py` — attacker simulation, action mechanics, team messages: all unchanged
- `tasks.py` — the 3 scenarios are already good
- `models.py` state schema — just add new models, don't change existing
- `server/app.py` skeleton, `pyproject.toml`, `openenv.yaml`, `Dockerfile`, `uv.lock`
- Stdout format (`log_start`, `log_step`, `log_end`)
- LocalEnv fallback pattern in `inference.py`

## Training Pipeline

**Setup:**
- Both agents: **Qwen2.5-3B-Instruct** (Colab free-tier T4)
- Framework: **TRL + GRPO**

**Two-phase training:**

### Phase 1: Commander (reuse Bastion v1 training)
- Run base Commander on 100 episodes to collect trajectories
- GRPO training 200 steps
- This is exactly what Bastion v1 training was supposed to be — same reward signal

### Phase 2: Oversight on fixed Commander
- Freeze trained Commander from Phase 1
- Oversight observes Commander's proposed actions, picks approve/veto/demand/flag
- Reward based on counterfactual (rerun with oversight's choice applied)
- GRPO training 200 steps

This is tractable because each phase is a single-agent problem.

**Deliverables:**
1. `training/train_commander.ipynb` + `training/train_oversight.ipynb`
2. Two reward curves (one per agent)
3. Before/after table with 4 rows:
   - Commander-only baseline
   - Commander-only trained
   - Commander+random-oversight
   - Commander+trained-oversight (should be best)
4. 2-min demo video

**Expected improvement:**
- Commander-only baseline: final_score ~0.45
- Trained Commander+Trained Oversight: final_score ~0.75
- Oversight's *own* accuracy (veto precision): 35% → 78%

## Implementation Schedule (2-3 days)

| Day | Work |
|---|---|
| **Day 1 AM** | `cp -r Stratagem Sentinel`. Add oversight models to `models.py`. Write `oversight_env.py` wrapper. |
| **Day 1 PM** | Extend `environment.py` for two-agent step loop. Extend `reward.py` with oversight reward + counterfactual logic. |
| **Day 2 AM** | Extend `inference.py` to drive both agents. Build `baseline.py` oversight policies. Get `openenv validate` passing. |
| **Day 2 PM** | Deploy new HF Space `Astro-Dude/sentinel`. Smoke test end-to-end with dummy LLM. |
| **Day 3 AM** | Train Commander (reuse Bastion training). Train Oversight on frozen Commander. Generate reward curves. |
| **Day 3 PM** | Record 2-min demo video (show veto catching a false-positive isolation). Write HF blog. Rehearse pitch. |

## Pitch Outline (3 min)

**Opening hook (25s):**
> "Last round we built Bastion — an RL environment to train AI security agents. It worked. But here's the thing: in the real world, nobody's going to let an AI isolate their production database without a human checking first. So how do we scale AI oversight when humans can't watch every action? We built an environment for training AI to watch AI. We call it Sentinel."

**Live demo (90s):**
- Screen 1: Commander sees a low-confidence alert on the firewall. Proposes `isolate(firewall)`. Without oversight, action executes, clean firewall goes down, service disrupted.
- Screen 2: Same episode, Sentinel's Oversight Agent sees the proposal, sees `action_based_on_investigated_system: false` and alert confidence 18%. Vetoes. Commander investigates first, finds firewall is clean. Crisis averted.
- Show two reward curves: Commander training (Bastion v1 continuation) + Oversight training (new). Both climb.
- Show the 4-row comparison table — trained pair wins.

**Technical depth (45s):**
- Multi-agent training: phase 1 trains commander, phase 2 trains oversight on fixed commander
- Oversight's reward uses **counterfactual rollouts** — did the veto actually improve outcomes?
- Qwen 2.5-3B on Colab free tier, 200 GRPO steps per agent
- Directly matches Fleet AI scalable oversight sub-theme

**Why it matters (20s):**
- Scalable oversight is a billion-dollar problem. You can't deploy autonomous AI agents in consequential domains (security, healthcare, finance) without it.
- Sentinel is the first open RL environment specifically for training oversight agents on adversarial security scenarios.

**Close (10s):**
> "Sentinel. Teaching AI to watch AI. Because the stakes are real."

## Verification Plan

Before submission:
1. `openenv validate .` passes all 4 deployment modes
2. `python inference.py` runs all 3 tasks with both agents, no crashes, using LocalEnv fallback
3. Stdout format matches `[START]/[STEP]/[END]` exactly
4. HF Space `Astro-Dude/sentinel` deploys, `/health` → 200, `/reset` → 200
5. Both Colab notebooks run end-to-end
6. Two reward curves saved to `training/`
7. Oversight catches a specific false-positive in demo footage (scripted/repeatable)
8. Final scores in [0, 1] for all tasks

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Counterfactual reward is too compute-heavy | Precompute 5-10 counterfactual rollouts per task offline; during training, sample from this precomputed bank |
| Two-agent training doesn't converge in 2 hrs | Keep training phases sequential (freeze one, train the other); avoid joint training |
| Oversight becomes trivially "approve everything" | Reward function explicitly penalizes over-permissiveness; baseline comparison ensures doing nothing isn't optimal |
| Judges confused by multi-agent complexity | Pitch opens with concrete veto example — judges see the concept immediately |
| Demo video too long | Pre-record both agent streams, edit side-by-side to 90s |

## Why This Wins

1. **Actually matters**: Scalable oversight is a top-5 unsolved problem in AI safety. Judges who care about AI-that-matters will light up.
2. **Direct Fleet AI sub-theme match** — extra prize pool access.
3. **Strong narrative continuity**: "Round 1 built the agent, Round 2 built the oversight for the agent." Judges respect iteration.
4. **~60% code reuse from working Bastion** — realistic for 2-3 days.
5. **Two reward curves** — double the "showing improvement" points.
6. **Demo is dramatic**: watching an AI catch another AI's mistake in real time is memorable.
7. **Your Scaler AI Labs multi-agent expertise** applies directly — this is exactly the category of work you've done.
