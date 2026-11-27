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

    # invoices and payments
    def create_invoice(self, task_id, due_date=None, notes="", user_name="system") -> dict:
        from datetime import date
        task_id = clean_id(task_id, "task id")
        if due_date:
            due_date = clean_text(due_date, "due_date", max_len=10)
            try:
                date.fromisoformat(due_date)
            except ValueError:
                raise ValidationError("due_date must use YYYY-MM-DD format") from None
        notes = clean_text(notes, "notes", required=False, max_len=1000)
        return self.db.create_invoice(
            task_id, due_date=due_date, notes=notes,
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def issue_invoice(self, invoice_id, user_name="system") -> dict:
        return self.db.issue_invoice(
            clean_id(invoice_id, "invoice id"),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def record_payment(self, invoice_id, data: dict, user_name="system") -> dict:
        from datetime import date
        if not isinstance(data, dict):
            raise ValidationError("payment must be an object")
        payment_date = clean_text(data.get("payment_date"), "payment_date", max_len=10)
        try:
            date.fromisoformat(payment_date)
        except ValueError:
            raise ValidationError("payment_date must use YYYY-MM-DD format") from None
        method = clean_choice(
            data.get("method") or "other", "method",
            ("cash", "bank_transfer", "card", "online", "other"),
        )
        reference = clean_text(data.get("reference"), "reference", required=False, max_len=100)
        return self.db.record_payment(
            clean_id(invoice_id, "invoice id"),
            clean_amount(data.get("amount"), "amount", allow_zero=False),
            clean_currency(data.get("currency") or self.settings.default_currency),
            payment_date, method, reference or None,
            clean_text(data.get("note"), "note", required=False, max_len=500),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def void_invoice(self, invoice_id, reason, user_name="system") -> dict:
        invoice_id = clean_id(invoice_id, "invoice id")
        reason = clean_text(reason, "reason", max_len=500)
        return self.db.void_invoice(
            invoice_id, reason,
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def refund_payment(self, payment_id, data: dict, user_name="system") -> dict:
        from datetime import date
        if not isinstance(data, dict):
            raise ValidationError("refund must be an object")
        refund_date = clean_text(data.get("refund_date"), "refund_date", max_len=10)
        try:
            date.fromisoformat(refund_date)
        except ValueError:
            raise ValidationError("refund_date must use YYYY-MM-DD format") from None
        reference = clean_text(data.get("reference"), "reference", required=False, max_len=100)
        note = clean_text(data.get("note"), "note", required=False, max_len=500)
        return self.db.refund_payment(
            clean_id(payment_id, "payment id"),
            clean_amount(data.get("amount"), "amount", allow_zero=False),
            refund_date, reference or None, note,
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    # ledger
    def add_ledger(self, data: dict, user_name: str = "system") -> dict:
        return self.db.add_ledger_entry(
            validate_ledger_entry(data, self.settings.default_currency),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def update_ledger(self, entry_id, data: dict, user_name: str = "system") -> dict:
        return self.db.update_ledger_entry(
            clean_id(entry_id, "ledger entry id"),
            validate_ledger_entry(data, self.settings.default_currency),
            user_name=clean_text(user_name, "user_name", max_len=100),
        )

    def delete_ledger(self, entry_id, user_name: str = "system") -> None:
        self.db.delete_ledger_entry(
            clean_id(entry_id, "ledger entry id"),
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
