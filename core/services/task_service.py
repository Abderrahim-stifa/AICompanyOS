"""Validated task operations backed by the transactional Database API."""
from core.services.base_service import BaseService
from core.validator import (
    TASK_STATUSES,
    clean_amount,
    clean_choice,
    clean_currency,
    clean_id,
    clean_text,
    validate_task,
)


class TaskService(BaseService):
    def __init__(self, database, default_currency="USD"):
        super().__init__(database)
        self.default_currency = default_currency

    def create_task(self, data, user_name="Admin"):
        cleaned = validate_task(data, self.default_currency)
        # Database writes CREATE audit data in the same SQLite transaction.
        return self.db.add_task(cleaned, user_name=user_name)

    def update_task(self, task_id, data, user_name="Admin"):
        task_id = clean_id(task_id, "task id")
        if not isinstance(data, dict):
            raise ValueError("task must be an object")
        allowed = {
            "title": lambda value: clean_text(value, "title", max_len=200),
            "description": lambda value: clean_text(value, "description", required=False, max_len=5000),
            "source": lambda value: clean_text(value, "source", required=False, max_len=200),
            "category": lambda value: clean_text(value, "category", required=False, max_len=100),
            "agent": lambda value: clean_text(value, "agent", required=False, max_len=100),
            "status": lambda value: clean_choice(value, "status", TASK_STATUSES),
            "priority": lambda value: clean_choice(value, "priority", ("low", "normal", "high", "urgent")),
            "price": lambda value: clean_amount(value, "price"),
            "currency": lambda value: clean_currency(value),
        }
        cleaned = {key: cleaner(data[key]) for key, cleaner in allowed.items() if key in data and data[key] is not None}
        return self.db.update_task(task_id, user_name=user_name, **cleaned)

    def delete_task(self, task_id, user_name="Admin"):
        return self.db.delete_task(clean_id(task_id, "task id"), user_name=user_name)

    def get_task(self, task_id):
        return self.db.get_task(clean_id(task_id, "task id"))

    def list_tasks(self, status=None):
        if status is not None:
            status = clean_choice(status, "status", TASK_STATUSES)
        return self.db.list_tasks(status)
