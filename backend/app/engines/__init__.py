"""Engine registry. `get_engine(name)` is the only thing the API imports."""

from __future__ import annotations

from .base import TranscriptionEngine

_REGISTRY = {}


def get_engine(name: str) -> TranscriptionEngine:
    if name in _REGISTRY:
        return _REGISTRY[name]

    if name == "heuristic":
        from .heuristic import HeuristicEngine
        _REGISTRY[name] = HeuristicEngine()
    elif name == "omnizart":
        from .omnizart_worker import OmnizartEngine
        _REGISTRY[name] = OmnizartEngine()
    else:
        raise ValueError(f"unknown engine '{name}' (have: heuristic, omnizart)")

    return _REGISTRY[name]


__all__ = ["get_engine", "TranscriptionEngine"]
