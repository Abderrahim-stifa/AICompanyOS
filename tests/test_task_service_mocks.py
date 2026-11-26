"""Unit tests for TaskService dependency injection with mocks."""
from unittest.mock import Mock

from core.services.task_service import TaskService


def test_create_task_calls_repository_and_logger():
    mock_repo = Mock()
    mock_logger = Mock()
    mock_repo.create.return_value = {"id": 10, "title": "Task A"}

    service = TaskService(default_currency="MAD", task_repository=mock_repo,
                          activity_logger=mock_logger)
    result = service.create_task({"title": "Task A"}, user_name="Admin")

    assert result["id"] == 10
    mock_repo.create.assert_called_once()
    mock_logger.log.assert_called_once()
    assert mock_logger.log.call_args.kwargs["action"] == "CREATE"
    assert mock_logger.log.call_args.kwargs["new_values"]["title"] == "Task A"


def test_update_task_calls_repository_and_logger_with_snapshots():
    mock_repo = Mock()
    mock_logger = Mock()
    mock_repo.get_by_id.return_value = {"id": 1, "title": "Old Title"}
    mock_repo.update.return_value = {"id": 1, "title": "New Title"}

    service = TaskService(default_currency="MAD", task_repository=mock_repo,
                          activity_logger=mock_logger)
    updated = service.update_task(1, {"title": "New Title"}, user_name="Admin")

    assert updated["title"] == "New Title"
    mock_repo.get_by_id.assert_called_once_with(1)
    mock_repo.update.assert_called_once_with(
        1, {"title": "New Title"}, user_name="Admin"
    )
    mock_logger.log.assert_called_once()
    audit = mock_logger.log.call_args.kwargs
    assert audit["action"] == "UPDATE"
    assert audit["old_values"]["title"] == "Old Title"
    assert audit["new_values"]["title"] == "New Title"
