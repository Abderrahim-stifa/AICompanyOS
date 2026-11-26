"""Validated task use-cases with injectable persistence and logging adapters."""
from core.services.base_service import BaseService
from core.services.interfaces import ITaskService
from core.repositories.task_repository import TaskRepository
from core.validator import TASK_STATUSES, clean_amount, clean_choice, clean_currency, clean_id, clean_text, validate_task


class TaskService(BaseService, ITaskService):
    def __init__(self, database=None, default_currency="USD", *, task_repository=None, activity_logger=None):
        # Preserve Company(database, currency) while allowing injected adapters.
        if task_repository is None:
            if database is None:
                raise ValueError("database or task_repository is required")
            task_repository = TaskRepository(database)
        resolved_database = database or getattr(task_repository, "database", None)
        super().__init__(resolved_database, activity_logger=activity_logger)
        self.task_repository = task_repository
        self.default_currency = default_currency

    def log_activity(self, action, entity_type, entity_id, user_name, details=""):
        """Log auxiliary events through the injected activity logger."""
        return super().log(action, entity_type, entity_id, user_name, details)

    def create_task(self, data, user_name="system"):
        cleaned = validate_task(data, self.default_currency)
        created = self.task_repository.create(cleaned, user_name=user_name)
        # The SQLite repository writes the audit row in the same transaction.
        # Other injected repositories delegate audit persistence to the logger.
        if not isinstance(self.task_repository, TaskRepository) and self.activity_logger is not None:
            self.activity_logger.log(
                action="CREATE", entity_type="TASK", entity_id=created["id"],
                user_name=user_name, details=created.get("title", ""),
                old_values=None, new_values=created,
            )
        return created

    def update_task(self, task_id, data, user_name="system"):
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
        cleaned = {key: cleaner(data[key]) for key, cleaner in allowed.items()
                   if key in data and data[key] is not None}
        old_task = None
        if not isinstance(self.task_repository, TaskRepository):
            old_task = self.task_repository.get_by_id(task_id)
        updated = self.task_repository.update(task_id, cleaned, user_name=user_name)
        if old_task is not None and self.activity_logger is not None:
            self.activity_logger.log(
                action="UPDATE", entity_type="TASK", entity_id=task_id,
                user_name=user_name, details=updated.get("title", ""),
                old_values=old_task, new_values=updated,
            )
        return updated

    def delete_task(self, task_id, user_name="system"):
        task_id = clean_id(task_id, "task id")
        old_task = None
        if not isinstance(self.task_repository, TaskRepository):
            old_task = self.task_repository.get_by_id(task_id)
        result = self.task_repository.delete(task_id, user_name=user_name)
        if old_task is not None and self.activity_logger is not None:
            self.activity_logger.log(
                action="DELETE", entity_type="TASK", entity_id=task_id,
                user_name=user_name, details=old_task.get("title", ""),
                old_values=old_task, new_values=None,
            )
        return result

    def get_task(self, task_id):
        return self.task_repository.get_by_id(clean_id(task_id, "task id"))

    def list_tasks(self, status=None):
        if status is not None:
            status = clean_choice(status, "status", TASK_STATUSES)
        return self.task_repository.list(status)
