"""
Stub for openenv.core.env_server — replaces the Meta OpenEnv SDK dependency.
"""
from __future__ import annotations
from typing import Generic, TypeVar

A = TypeVar("A")
O = TypeVar("O")
S = TypeVar("S")


class Action:
    pass


class Observation:
    pass


class State:
    pass


class Environment(Generic[A, O, S]):
    """Minimal base class — matches the interface CitadelEnvironment expects."""

    def reset(self, **kwargs):
        raise NotImplementedError

    def step(self, action: A) -> O:
        raise NotImplementedError

    def render(self):
        pass
