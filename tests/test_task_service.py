"""TaskService integration tests against an isolated application database."""
import pytest

from core.services.task_service import TaskService


def test_create_task_records_actor_and_entity(temp_db):
    service = TaskService(temp_db, default_currency="MAD")
    task = service.create_task({"title": "Task A"}, user_name="Creator")

    assert task["title"] == "Task A"
    event = temp_db.list_system_logs()[0]
    assert (event["action"], event["entity_type"], event["entity_id"], event["user_name"]) == (
        "CREATE", "TASK", task["id"], "Creator"
    )


def test_update_task_records_actor_and_entity(temp_db, sample_task):
    service = TaskService(temp_db, default_currency="MAD")
    updated = service.update_task(sample_task["id"], {"title": "Updated"}, user_name="Editor")

    assert updated["title"] == "Updated"
    event = temp_db.list_system_logs()[0]
    assert (event["action"], event["entity_id"], event["user_name"]) == (
        "UPDATE", sample_task["id"], "Editor"
    )


def test_delete_task_records_actor_and_entity(temp_db, sample_task):
    service = TaskService(temp_db, default_currency="MAD")
    service.delete_task(sample_task["id"], user_name="Owner")

    assert temp_db.list_tasks() == []
    event = temp_db.list_system_logs()[0]
    assert (event["action"], event["entity_type"], event["entity_id"], event["user_name"]) == (
        "DELETE", "TASK", sample_task["id"], "Owner"
    )


def test_invalid_task_input_is_rejected(temp_db):
    service = TaskService(temp_db, default_currency="MAD")
    with pytest.raises(ValueError):
        service.create_task({"title": ""})
