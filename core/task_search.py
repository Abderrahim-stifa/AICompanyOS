"""Fast, case-insensitive task search helpers."""
from __future__ import annotations


def search_tasks(
    tasks: list[dict],
    query: str,
    clients: list[dict] | None = None,
    projects: list[dict] | None = None,
) -> list[dict]:
    """Filter tasks by title, description, or linked client name."""
    normalized_query = (query or "").strip().casefold()
    if not normalized_query:
        return list(tasks)

    client_names = {
        client.get("id"): str(client.get("name", ""))
        for client in (clients or [])
    }
    project_names = {
        project.get("id"): str(project.get("name", ""))
        for project in (projects or [])
    }
    matches = []
    for task in tasks:
        searchable = " ".join(
            str(value or "")
            for value in (
                task.get("title", ""),
                task.get("description", ""),
                client_names.get(task.get("client_id"), ""),
                project_names.get(task.get("project_id"), ""),
            )
        ).casefold()
        if normalized_query in searchable:
            matches.append(task)
    return matches
