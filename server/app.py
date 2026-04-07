"""
Bastion: Cybersecurity Incident Response — Server Entry Point
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openenv.core.env_server import create_app

from models import IncidentAction, IncidentObservation
from environment import BastionEnvironment

app = create_app(
    env=BastionEnvironment,
    action_cls=IncidentAction,
    observation_cls=IncidentObservation,
    env_name="bastion",
)


@app.get("/")
def root():
    return {
        "name": "Bastion",
        "description": "Cybersecurity Incident Response RL Environment",
        "endpoints": {
            "health": "GET /health",
            "schema": "GET /schema",
            "reset": "POST /reset {task_id: easy_1|medium_1|hard_1}",
            "step": "POST /step {action: 0-9, target_system: 0-7}",
            "state": "GET /state",
            "websocket": "WS /ws",
        },
        "tasks": ["easy_1 (Script Kiddie)", "medium_1 (Ransomware)", "hard_1 (APT)"],
        "status": "running",
    }


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
