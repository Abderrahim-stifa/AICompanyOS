"""Compatibility-facing registry for the seven local role agents.

The canonical implementation remains in core.ai_agents so existing imports and
stored data keep working while the project moves toward the planned ai/ package.
"""
from core.ai_agents import AGENTS, COMMON, run_agent

__all__ = ["AGENTS", "COMMON", "run_agent"]
