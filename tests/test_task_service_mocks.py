"""Unit tests for TaskService dependency injection with mocks."""
from unittest.mock import Mock

from core.services.task_service import TaskService


def test_create_task_delegates_to_repository_and_logger_contract():
    mock_repo = Mock()
    mock_logger = Mock()
    mock_repo.create.return_value = {"id": 10, "title": "Task A"}

    service = TaskService(
        default_currency="MAD",
        task_repository=mock_repo,
        activity_logger=mock_logger,
    )
    result = service.create_task({"title": "Task A"}, user_name="Admin")

    assert result["id"] == 10
    mock_repo.create.assert_called_once()
    service.log_activity("CREATE_NOTE", "TASK", 10, "Admin", "mock audit")
    mock_logger.log.assert_called_once_with(
        action="CREATE_NOTE", entity_type="TASK", entity_id=10,
        user_name="Admin", details="mock audit",
    )


def test_update_task_reads_old_and_new_state_and_delegates_update():
    mock_repo = Mock()
    mock_logger = Mock()
    mock_repo.get_by_id.side_effect = [
        {"id": 1, "title": "Old Title"},
        {"id": 1, "title": "New Title"},
    ]
    mock_repo.update.return_value = {"id": 1, "title": "New Title"}

    service = TaskService(
        default_currency="MAD",
        task_repository=mock_repo,
        activity_logger=mock_logger,
    )
    old_task = mock_repo.get_by_id(1)
    updated = service.update_task(1, {"title": "New Title"}, user_name="Admin")
    new_task = mock_repo.get_by_id(1)

    assert old_task["title"] == "Old Title"
    assert updated["title"] == "New Title"
    assert new_task["title"] == "New Title"
    mock_repo.update.assert_called_once_with(1, {"title": "New Title"}, user_name="Admin")
    service.log_activity("UPDATE_NOTE", "TASK", 1, "Admin", "mock audit")
    mock_logger.log.assert_called_once()
