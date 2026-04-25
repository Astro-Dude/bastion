"""
Stub for openenv.core.env_server — replaces the Meta OpenEnv SDK dependency.
CitadelEnvironment subclasses Environment[A, O, S]; this stub makes it a
plain Python generic base so the code runs without the hackathon's SDK.
"""
from __future__ import annotations
from typing import Generic, TypeVar

A = TypeVar("A")
O = TypeVar("O")
S = TypeVar("S")


class Environment(Generic[A, O, S]):
    """Minimal base class — matches the interface CitadelEnvironment expects."""

    def reset(self, **kwargs):
        raise NotImplementedError

    def step(self, action: A) -> O:
        raise NotImplementedError

    def render(self):
        pass
