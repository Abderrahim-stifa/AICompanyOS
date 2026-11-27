"""Read-only overview helpers for the seven role-based agents."""
from __future__ import annotations

from core.ai_agents import AGENTS


ACTIVE_TASK_STATES = {"assigned", "in_progress"}
COMPLETED_TASK_STATES = {"done"}


def build_agent_overview(tasks: list[dict], enabled: dict[str, bool] | None = None) -> list[dict]:
    """Return task counters and derived status for every registered role agent.

    A task belongs to an agent when its agent field matches the registry key,
    English display name, or Arabic display name. Pipeline agents are intentionally
    not mixed into this seven-role overview.
    """
    enabled = enabled or {}
    overview = []
    for key, definition in AGENTS.items():
        identifiers = {key, definition["name"], definition["name_ar"]}
        # role_agent_key is the canonical specialist assignment. The legacy
        # agent fallback keeps historical rows and older callers readable,
        # while pipeline-only values (manager/finder/classifier/executor) never
        # count as assignments to one of the seven role agents.
        assigned = [
            task for task in tasks
            if task.get("role_agent_key") == key
            or (not task.get("role_agent_key") and task.get("agent") in identifiers)
        ]
        active = sum(task.get("status") in ACTIVE_TASK_STATES for task in assigned)
        completed = sum(task.get("status") in COMPLETED_TASK_STATES for task in assigned)
        is_enabled = bool(enabled.get(key, True))
        status = "disabled" if not is_enabled else ("active" if active else "ready")
        overview.append({
            "key": key,
            "name": definition["name"],
            "name_ar": definition["name_ar"],
            "purpose": definition["purpose"],
            "enabled": is_enabled,
            "status": status,
            "task_count": len(assigned),
            "active_task_count": active,
            "completed_task_count": completed,
        })
    return overview
