"""
Bastion — Cybersecurity Incident Response Inference Script
===================================
MANDATORY env vars: API_BASE_URL, MODEL_NAME, HF_TOKEN
STDOUT FORMAT: [START], [STEP], [END]
"""

import asyncio
import json
import os
import re
import sys
import textwrap
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from openai import OpenAI

from models import IncidentAction, IncidentObservation, ACTION_NAMES, NUM_ACTIONS, SYSTEM_NAMES
from environment import BastionEnvironment

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
HF_TOKEN = os.getenv("HF_TOKEN")

# Optional — if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

API_KEY = HF_TOKEN

BENCHMARK = "bastion"
MAX_STEPS = 12
TEMPERATURE = 0.3
MAX_TOKENS = 400
TASKS = ["easy_1", "medium_1", "hard_1"]


# ---------------------------------------------------------------------------
# Local environment wrapper (matches EnvClient StepResult interface)
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    observation: IncidentObservation
    reward: Optional[float] = None
    done: bool = False


class LocalEnv:
    """Wraps BastionEnvironment to match the async EnvClient interface."""

    def __init__(self) -> None:
        self._env = BastionEnvironment()

    async def reset(self, **kwargs: Any) -> StepResult:
        obs = self._env.reset(**kwargs)
        return StepResult(observation=obs, reward=obs.reward, done=obs.done)

    async def step(self, action: IncidentAction) -> StepResult:
        obs = self._env.step(action)
        return StepResult(observation=obs, reward=obs.reward, done=obs.done)

    async def close(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Structured stdout logging
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}", flush=True)

def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    You are an expert Incident Commander responding to a live cyberattack on a corporate network.

    ## Network (8 systems, indexed 0-7):
    0: web_server    1: app_server    2: database      3: file_server
    4: email_server  5: workstations  6: backup_server  7: firewall

    ## Actions (pick action 0-9 and target system 0-7):
    0: investigate_system  — Reveals true state of target. Costs stamina. Takes time.
    1: isolate_system      — Cuts target from network. Stops attacker BUT kills service.
    2: patch_vulnerability  — Fixes vuln on target. Slow, may clean compromised systems.
    3: restore_from_backup  — Restores target from backup. DANGER: backup may be compromised.
    4: analyze_alerts       — Deep analysis of alert queue. Reveals true/false positives.
    5: deploy_monitoring    — Adds sensors to target + neighbors. Improves future detection.
    6: escalate_to_management — Gets resources but adds scrutiny pressure.
    7: block_external_traffic — Stops ALL outbound connections. Kills exfiltration + services.
    8: hunt_threat          — Proactively search target for attacker indicators.
    9: coordinate_team      — Rest and regroup. Recovers stamina but wastes an hour.

    ## Key dynamics:
    - Attacker moves laterally through connected systems each hour
    - Attacker exfiltrates data from database, file_server, email_server, backup_server
    - Compromise is UNKNOWN until you investigate or hunt a system
    - Alerts may be FALSE POSITIVES — analyze_alerts reveals which are real
    - Team stamina depletes with actions; exhausted team is less effective
    - Restoring from a compromised backup re-infects the target!
    - Blocking external traffic stops exfiltration but disrupts all services

    ## Scoring:
    35% data protection + 25% containment + 20% business continuity + 10% forensics + 10% team health

    ## Strategy tips:
    - INVESTIGATE before acting blindly
    - Prioritize isolating CONFIRMED compromised systems adjacent to critical data
    - Don't isolate everything — you need services running
    - Deploy monitoring EARLY for better future alerts
    - Watch your team stamina — coordinate_team recovers it

    Respond with ONLY: {"action": <0-9>, "target": <0-7>, "reasoning": "<brief>"}
""")


# ---------------------------------------------------------------------------
# Observation formatting
# ---------------------------------------------------------------------------

def format_observation(obs: dict, step: int, history: List[str]) -> str:
    parts = []

    if step == 0:
        desc = obs.get("task_description", "")
        if desc:
            parts.append(f"## Incident Brief\n{desc}\n")

    parts.append(f"## Hour {obs.get('hour', 0)} Status (Hours remaining: {obs.get('hours_remaining', 12)})")
    parts.append(f"- Breach severity: {obs.get('estimated_breach_severity', 'unknown')}")
    parts.append(f"- Data at risk: {obs.get('estimated_data_at_risk', 0):.0%}")
    parts.append(f"- Services disrupted: {obs.get('services_disrupted', 0)}/{obs.get('services_total', 4)}")
    parts.append(f"- Team stamina: {obs.get('team_stamina', 1.0):.0%}")
    parts.append(f"- External traffic blocked: {obs.get('external_blocked', False)}")
    parts.append(f"- Management escalated: {obs.get('management_escalated', False)}")

    systems = obs.get("systems_visible", [])
    if systems:
        parts.append("\n## Systems")
        for s in systems:
            status_parts = []
            comp = s.get("compromised", "unknown")
            if comp == "unknown":
                status_parts.append("compromise=?")
            else:
                status_parts.append(f"compromised={'YES' if comp else 'no'}")
            if s.get("isolated"):
                status_parts.append("ISOLATED")
            if s.get("investigated"):
                status_parts.append("investigated")
            if s.get("patched"):
                status_parts.append("patched")
            status_parts.append(f"integrity={s.get('integrity', 1.0):.0%}")
            status_parts.append(f"monitoring={s.get('monitoring_level', 0)}")
            idx = SYSTEM_NAMES.index(s['name']) if s['name'] in SYSTEM_NAMES else 0
            parts.append(f"  [{idx}] {s['name']:16s} | {', '.join(status_parts)}")

    alerts = obs.get("alert_queue", [])
    if alerts:
        parts.append("\n## SIEM Alert Queue")
        for a in alerts[-4:]:
            confirmed = a.get("confirmed", "")
            conf_str = f" [{'CONFIRMED' if confirmed else 'FALSE POSITIVE'}]" if confirmed != "" else ""
            eid = a.get("event_id", "")
            eid_str = f"[{eid}] " if eid else ""
            parts.append(f"  {eid_str}[{a.get('severity', '?'):8s}] {a.get('message', '')}{conf_str}")
            # SIEM detail line
            details = []
            if a.get("mitre_technique"):
                details.append(f"MITRE:{a['mitre_tactic']}({a['mitre_technique']})")
            if a.get("source_ip") or a.get("dest_ip"):
                details.append(f"src={a.get('source_ip','?')}→dst={a.get('dest_ip','?')}")
            if a.get("process_name"):
                details.append(f"proc={a['process_name']}")
            if a.get("confidence"):
                details.append(f"conf={a['confidence']:.0%}")
            if a.get("file_hash"):
                details.append(f"hash={a['file_hash'][:24]}...")
            if details:
                parts.append(f"           {' | '.join(details)}")

    if history:
        parts.append("\n## Your recent actions")
        for h in history[-3:]:
            parts.append(f"  {h}")

    parts.append('\nRespond: {"action": <0-9>, "target": <0-7>, "reasoning": "..."}')
    return "\n".join(parts)


def parse_response(text: str) -> tuple[int, int]:
    """Extract action and target from LLM response."""
    json_match = re.search(r'\{[^}]*"action"\s*:\s*(\d)[^}]*\}', text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            action = int(data.get("action", 9))
            target = int(data.get("target", 0))
            if 0 <= action < NUM_ACTIONS and 0 <= target < len(SYSTEM_NAMES):
                return action, target
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return 9, 0  # fallback: coordinate_team


# ---------------------------------------------------------------------------
# Run one task
# ---------------------------------------------------------------------------

async def run_task(env, task_id: str, client: OpenAI) -> float:
    history: List[str] = []
    messages: List[Dict[str, str]] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset(task_id=task_id)
        obs = result.observation.model_dump()

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            user_msg = format_observation(obs, step - 1, history)
            messages.append({"role": "user", "content": user_msg})

            try:
                completion = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + messages[-6:],
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    stream=False,
                )
                llm_text = (completion.choices[0].message.content or "").strip()
            except Exception as exc:
                print(f"[DEBUG] LLM error: {exc}", flush=True)
                llm_text = '{"action": 9, "target": 0, "reasoning": "API error fallback"}'

            messages.append({"role": "assistant", "content": llm_text})
            action_idx, target_idx = parse_response(llm_text)
            action_name = f"{ACTION_NAMES.get(action_idx, str(action_idx))}({SYSTEM_NAMES[target_idx]})"

            result = await env.step(IncidentAction(action=action_idx, target_system=target_idx))
            obs = result.observation.model_dump()
            reward = result.reward or 0.0
            done = result.done
            error = None
            if isinstance(obs.get("metadata"), dict):
                error = obs["metadata"].get("error")

            rewards.append(reward)
            steps_taken = step

            log_step(step=step, action=action_name, reward=reward, done=done, error=error)
            history.append(f"Hour {step}: {action_name} -> reward {reward:+.2f}")

            if done:
                meta = result.observation.metadata or {}
                score = meta.get("comparison_score", 0.5)
                score = min(max(score, 0.0), 1.0)
                success = score >= 0.5
                break

        if not result.done:
            score = 0.5
            success = True

    except Exception as exc:
        print(f"[DEBUG] Task {task_id} error: {exc}", flush=True)
        score = 0.0
        success = False

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


# ---------------------------------------------------------------------------
# Create environment (Docker → HF Space → Local fallback)
# ---------------------------------------------------------------------------

async def create_env():
    """Try Docker image first, then HF Space, then local environment."""

    # 1. Try Docker if LOCAL_IMAGE_NAME is set
    if LOCAL_IMAGE_NAME:
        try:
            from client import BastionEnv
            print(f"[DEBUG] Trying Docker image: {LOCAL_IMAGE_NAME}", flush=True)
            env = await BastionEnv.from_docker_image(LOCAL_IMAGE_NAME)
            print("[DEBUG] Docker environment connected", flush=True)
            return env
        except Exception as e:
            print(f"[DEBUG] Docker failed: {e}", flush=True)

    # 2. Try connecting to HF Space
    hf_space_url = os.getenv("HF_SPACE_URL", "https://astro-dude-bastion.hf.space")
    try:
        from client import BastionEnv
        print(f"[DEBUG] Trying HF Space: {hf_space_url}", flush=True)
        env = BastionEnv(base_url=hf_space_url)
        await env.connect()
        print("[DEBUG] HF Space environment connected", flush=True)
        return env
    except Exception as e:
        print(f"[DEBUG] HF Space failed: {e}", flush=True)

    # 3. Fallback to local environment (always works)
    print("[DEBUG] Using local environment", flush=True)
    return LocalEnv()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = await create_env()

    try:
        for task_id in TASKS:
            await run_task(env, task_id, client)
    finally:
        try:
            await env.close()
        except Exception as e:
            print(f"[DEBUG] env.close() error: {e}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
