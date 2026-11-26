"""Business logic shared by the dashboard (app.py), the CLI and the HTTP API (cli.py).

Every write goes through the validators here, so the UI layers never touch raw input.
"""
from __future__ import annotations

from .database import Database
from .init_db import initialize_database
from .logs import setup_logging
from .settings import load_settings
from .validator import (
    PROJECT_STATUSES,
    TASK_STATUSES,
    clean_choice,
    clean_id,
    clean_text,
    validate_client,
    validate_ledger_entry,
    validate_project,
    validate_task,
)


class Company:
    def __init__(self):
        self.settings = load_settings()
        setup_logging(self.settings.log_dir, self.settings.log_level)
        initialize_database(self.settings.db_path)
        self.db = Database(self.settings.db_path)

    # tasks
    def add_task(self, data: dict, user_name: str = "Admin") -> dict:
        return self.db.add_task(validate_task(data, self.settings.default_currency), user_name=user_name)

    def update_task(self, task_id, data: dict) -> dict:
        task_id = clean_id(task_id, "task id")
        status = data.get("status")
        category = data.get("category")
        agent = data.get("agent")
        title = data.get("title")
        description = data.get("description")
        priority = data.get("priority")
        if status is not None:
            status = clean_choice(status, "status", TASK_STATUSES)
        if category is not None:
            category = clean_text(category, "category", required=False, max_len=100)
        if agent is not None:
            agent = clean_text(agent, "agent", required=False, max_len=100)
        if title is not None:
            title = clean_text(title, "title", max_len=200)
        if description is not None:
            description = clean_text(description, "description", required=False, max_len=5000)
        if priority is not None:
            priority = clean_choice(priority, "priority", ("low", "normal", "high", "urgent"))
        return self.db.update_task(
            task_id, status=status, category=category, agent=agent,
            title=title, description=description, priority=priority,
        )

    def delete_task(self, task_id, user_name: str = "Admin") -> None:
        self.db.delete_task(clean_id(task_id, "task id"), user_name=user_name)

    def assign_role_agent(self, task_id, agent_key: str) -> dict:
        task_id = clean_id(task_id, "task id")
        agent_key = clean_text(agent_key, "agent key", max_len=80)
        return self.db.assign_role_agent(task_id, agent_key)

    def set_task_status(self, task_id, status: str) -> dict:
        task_id = clean_id(task_id, "task id")
        status = clean_choice(status, "status", TASK_STATUSES)
        return self.db.set_task_status(task_id, status)

    def save_task_result(self, task_id, result: str) -> dict:
        task_id = clean_id(task_id, "task id")
        result = clean_text(result, "result", max_len=20000)
        return self.db.save_task_result(task_id, result)

    # ledger
    def add_ledger(self, data: dict) -> dict:
        return self.db.add_ledger_entry(validate_ledger_entry(data, self.settings.default_currency))

    # clients
    def add_client(self, data: dict) -> dict:
        return self.db.add_client(validate_client(data))

    def update_client(self, client_id, data: dict) -> dict:
        return self.db.update_client(clean_id(client_id, "client id"), validate_client(data))

    def delete_client(self, client_id) -> None:
        self.db.delete_client(clean_id(client_id, "client id"))

    # projects
    def add_project(self, data: dict) -> dict:
        return self.db.add_project(validate_project(data, self.settings.default_currency))

    def update_project(self, project_id, data: dict) -> dict:
        return self.db.update_project(
            clean_id(project_id, "project id"),
            validate_project(data, self.settings.default_currency),
        )

    def set_project_status(self, project_id, status) -> None:
        self.db.set_project_status(
            clean_id(project_id, "project id"),
            clean_choice(status, "status", PROJECT_STATUSES),
        )

    def delete_project(self, project_id) -> None:
        self.db.delete_project(clean_id(project_id, "project id"))
