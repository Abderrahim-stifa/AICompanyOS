"""Repository and service failure-path tests for missing tasks."""
from unittest.mock import Mock

import pytest

from core.repositories.task_repository import TaskRepository
from core.services.task_service import TaskService


def test_update_non_existing_task(temp_db):
    repository = TaskRepository(temp_db)
    with pytest.raises(ValueError, match="not found"):
        repository.update(999, {"title": "Missing"}, user_name="Tester")


def test_delete_non_existing_task(temp_db):
    repository = TaskRepository(temp_db)
    with pytest.raises(ValueError, match="not found"):
        repository.delete(999, user_name="Tester")


def test_service_passes_update_error():
    mock_repo = Mock()
    mock_repo.get_by_id.return_value = {"id": 999, "title": "Missing"}
    mock_repo.update.side_effect = ValueError("Task not found")
    service = TaskService(
        default_currency="MAD",
        task_repository=mock_repo,
        activity_logger=Mock(),
    )

    with pytest.raises(ValueError, match="Task not found"):
        service.update_task(999, {"title": "Task"}, user_name="Tester")

    mock_repo.update.assert_called_once()
