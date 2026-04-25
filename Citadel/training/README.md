# Citadel — Training Pipeline

Two-phase GRPO training on **Qwen2.5-3B-Instruct** using TRL + Unsloth.
Runs on a free Colab T4 (16 GB) in under 20 minutes per phase.

## Files

| File | What it does |
|------|-------------|
| `grpo_train.py` | Phase 1 (Commander) + Phase 2 (Oversight) GRPO training |
| `eval_before_after.py` | Runs untrained vs trained on 12 episodes, produces comparison table + chart |
| `train_commander.ipynb` | Older notebook (superseded by grpo_train.py) |
| `train_oversight.ipynb` | Older notebook (superseded by grpo_train.py) |

---

## Colab Setup (exact steps)

### 1. Open a Colab T4 runtime
Runtime → Change runtime type → **T4 GPU**

### 2. Clone the repo and install
```python
!git clone https://huggingface.co/spaces/Astro-Dude/citadel /content/Citadel
%cd /content/Citadel

!pip install -q \
  "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git" \
  trl==0.11.4 peft==0.13.2 bitsandbytes==0.44.1 \
  accelerate datasets matplotlib \
  openenv-core fastapi uvicorn
```

### 3. Run Phase 1 — Train Commander (≈15 min on T4)
```python
import os
os.environ["MAX_STEPS"] = "120"
os.environ["N_SEEDS"]   = "6"
os.environ["PHASE"]     = "1"
os.environ["SAVE_DIR"]  = "/content/checkpoints"

!python /content/Citadel/training/grpo_train.py
```

Outputs:
- `/content/checkpoints/commander/final/` — LoRA adapter
- `/content/checkpoints/commander/reward_curve.json`
- `/content/checkpoints/commander/reward_curve.png`

### 4. Run Phase 2 — Train Oversight (≈15 min on T4)
```python
os.environ["PHASE"] = "2"
!python /content/Citadel/training/grpo_train.py
```

Outputs:
- `/content/checkpoints/oversight/final/`
- `/content/checkpoints/oversight/reward_curve.{json,png}`

### 5. Before / After evaluation
```python
!python /content/Citadel/training/eval_before_after.py \
    --trained_path /content/checkpoints/commander/final \
    --n_episodes 12 \
    --save_dir /content/checkpoints/eval
```

Outputs:
- `/content/checkpoints/eval/before_after_table.md` — markdown comparison table
- `/content/checkpoints/eval/before_after_chart.png` — bar chart (6 metrics × 2 models)
- `/content/checkpoints/eval/before_after.json` — raw episode data

### 6. Download results
```python
from google.colab import files
files.download('/content/checkpoints/commander/reward_curve.png')
files.download('/content/checkpoints/eval/before_after_chart.png')
files.download('/content/checkpoints/eval/before_after_table.md')
```

---

## What the training loop does

### Reward design (two independent functions — anti-hacking per guide §8)

**Outcome reward (75% weight)**
- Runs one env step with the Commander's parsed action
- Returns `commander_step_reward` from the environment (containment + exfil + governance + trust)
- Clipped to `[-1, 1]` for gradient stability

**Format reward (25% weight)**
- Checks if completion parses as valid JSON with `{action, target, justification}`
- Bonus for `method`, `rollback_plan`, `cited_lessons` — encourages rich output
- Returns `[-0.2, 0.35]`

### Curriculum (per guide §7 and §6)
| Steps | Tasks active | Adversary gens |
|-------|-------------|----------------|
| 0–40 | easy_1 only | Gen 1 |
| 40–80 | easy_1 + medium_1 | Gen 1, 2 |
| 80+ | all three tasks | Gen 1, 2, 3 |

### GRPO config
- `num_generations=4` — 4 rollouts per prompt, ranked by reward
- `learning_rate=5e-6` — conservative for RL stability
- `max_completion_length=300` — enough for full JSON + justification
- Unsloth 4-bit QLoRA: r=16, target all attention + MLP projections

---

## Expected improvement (after 120 steps on T4)

| Metric | Untrained | Trained (expected) | Why |
|--------|-----------|-------------------|-----|
| Final score | ~0.45 | ~0.62 | Learns investigate-before-isolate |
| Governance compliance | ~0.10 | ~0.45 | Learns CAB → notify → isolate chain |
| Data exfiltrated | ~0.55 | ~0.30 | Better containment priority |
| Investor satisfaction | ~0.35 | ~0.65 | Learns to post to #investor-relations |
| Oversight first-pass approve | ~50% | ~70% | Learns to write justified proposals |

---

## Saving the model correctly (per guide §16)

The training script saves LoRA adapters via `trainer.save_model()`.
**Do not merge to 16-bit naively.** To use the adapter in inference:

```python
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", ...)
model = PeftModel.from_pretrained(base, "/content/checkpoints/commander/final")
```

Or with Unsloth (recommended):
```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    "/content/checkpoints/commander/final", load_in_4bit=True
)
FastLanguageModel.for_inference(model)
```
