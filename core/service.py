"""Business logic shared by the dashboard (app.py), the CLI and the HTTP API (cli.py).

Every write goes through the validators here, so the UI layers never touch raw input.
"""
from __future__ import annotations

from .database import Database
from .init_db import initialize_database
from .logs import setup_logging
from .settings import load_settings
from .smart_agent import SmartTaskAnalyzer
from .services.task_service import TaskService
from .validator import (
    PROJECT_STATUSES,
    TASK_STATUSES,
    ValidationError,
    clean_choice,
    clean_id,
    clean_text,
    clean_amount,
    clean_currency,
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
        self.task_service = TaskService(self.db, self.settings.default_currency)

    # tasks
    def add_task(self, data: dict, user_name: str = "system") -> dict:
        return self.task_service.create_task(data, user_name=user_name)

    def add_task_analyzed(self, data: dict, user_name: str = "system") -> dict:
        """Add a task, classifying it locally when no category was given.

        Shared by the dashboard, the CLI and the HTTP API so all three behave alike.
        """
        if not isinstance(data, dict):
            raise ValidationError("task must be an object")
        data = dict(data)
        if not data.get("category"):
            analysis = SmartTaskAnalyzer.analyze_and_classify(
                f"{data.get('title') or ''} {data.get('description') or ''}"
            )
            data["category"] = analysis["category"]
            data.setdefault("priority", analysis["priority"])
        return self.add_task(data, user_name=user_name)

    def update_task(self, task_id, data: dict, user_name: str | None = None) -> dict:
        return self.task_service.update_task(
            task_id, data, user_name=user_name or data.get("user_name", "system")
        )

    def delete_task(self, task_id, user_name: str = "system") -> None:
        return self.task_service.delete_task(task_id, user_name=user_name)

    def assign_role_agent(self, task_id, agent_key: str, user_name: str = "system") -> dict:
        task_id = clean_id(task_id, "task id")
        agent_key = clean_text(agent_key, "agent key", max_len=80)
        user_name = clean_text(user_name, "user_name", max_len=100)
        return self.db.assign_role_agent(task_id, agent_key, user_name=user_name)

    def unassign_role_agent(self, task_id, user_name: str = "system") -> dict:
        task_id = clean_id(task_id, "task id")
        user_name = clean_text(user_name, "user_name", max_len=100)
        return self.db.unassign_role_agent(task_id, user_name=user_name)

    def set_task_status(self, task_id, status: str) -> dict:
        task_id = clean_id(task_id, "task id")
        status = clean_choice(status, "status", TASK_STATUSES)
        return self.db.set_task_status(task_id, status)

    def save_task_result(self, task_id, result: str) -> dict:
        task_id = clean_id(task_id, "task id")
        result = clean_text(result, "result", max_len=20000)
        return self.db.save_task_result(task_id, result)

    # ledger
    def add_ledger(self, data: dict, user_name: str = "system") -> dict:
        return self.db.add_ledger_entry(
            validate_ledger_entry(data, self.settings.default_currency),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    # clients
    def add_client(self, data: dict, user_name: str = "system") -> dict:
        return self.db.add_client(
            validate_client(data), user_name=clean_text(user_name, "user_name", max_len=100)
        )

    def update_client(self, client_id, data: dict, user_name: str = "system") -> dict:
        return self.db.update_client(
            clean_id(client_id, "client id"), validate_client(data),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def delete_client(self, client_id, user_name: str = "system") -> None:
        self.db.delete_client(
            clean_id(client_id, "client id"),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    # projects
    def add_project(self, data: dict, user_name: str = "system") -> dict:
        return self.db.add_project(
            validate_project(data, self.settings.default_currency),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def update_project(self, project_id, data: dict, user_name: str = "system") -> dict:
        return self.db.update_project(
            clean_id(project_id, "project id"),
            validate_project(data, self.settings.default_currency),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def set_project_status(self, project_id, status, user_name: str = "system") -> None:
        self.db.set_project_status(
            clean_id(project_id, "project id"),
            clean_choice(status, "status", PROJECT_STATUSES),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def delete_project(self, project_id, user_name: str = "system") -> None:
        self.db.delete_project(
            clean_id(project_id, "project id"),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )
