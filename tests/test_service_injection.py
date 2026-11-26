"""Dependency injection tests for task use-cases."""
from core.services.interfaces import IActivityLogger, ITaskRepository, ITaskService
from core.services.task_service import TaskService


class FakeRepository:
    def __init__(self):
        self.created = None

    def create(self, data, user_name="Admin"):
        self.created = (data, user_name)
        return {"id": 101, **data}

    def update(self, task_id, data, user_name="Admin"):
        return {"id": task_id, **data}

    def delete(self, task_id, user_name="Admin"):
        self.deleted = (task_id, user_name)

    def get_by_id(self, task_id):
        return {"id": task_id}

    def list(self, status=None):
        return []


class FakeLogger:
    def __init__(self):
        self.events = []

    def log(self, **event):
        self.events.append(event)


def test_service_accepts_injected_repository_and_logger():
    repository = FakeRepository()
    logger = FakeLogger()
    service = TaskService(default_currency="MAD", task_repository=repository, activity_logger=logger)

    created = service.create_task({"title": "Injected"}, user_name="Tester")
    assert created["id"] == 101
    assert repository.created[1] == "Tester"

    service.log_activity("EXPORT", "TASK", 101, "Tester", "manual event")
    assert logger.events[0]["action"] == "EXPORT"


def test_service_and_repository_satisfy_contracts(temp_db):
    service = TaskService(temp_db, default_currency="MAD")
    assert isinstance(service, ITaskService)
    assert isinstance(service.task_repository, ITaskRepository)
    assert isinstance(service.activity_logger, IActivityLogger)
