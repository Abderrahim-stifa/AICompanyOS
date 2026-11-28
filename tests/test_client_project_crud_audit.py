"""Regression coverage for client and project CRUD audit snapshots."""
import json


def test_client_update_and_delete_capture_actor_and_snapshots(temp_db):
    client = temp_db.add_client(
        {"name": "Original client", "email": "old@example.test", "phone": "111"},
        user_name="creator",
    )

    updated = temp_db.update_client(
        client["id"],
        {"name": "Updated client", "email": "new@example.test", "phone": "222"},
        user_name="editor",
    )
    update_event = temp_db.list_system_logs()[0]

    assert updated["name"] == "Updated client"
    assert update_event["action"] == "UPDATE"
    assert update_event["entity_type"] == "CLIENT"
    assert update_event["entity_id"] == client["id"]
    assert update_event["user_name"] == "editor"
    assert json.loads(update_event["old_values"])["email"] == "old@example.test"
    assert json.loads(update_event["new_values"])["email"] == "new@example.test"

    temp_db.delete_client(client["id"], user_name="deleter")
    delete_event = temp_db.list_system_logs()[0]

    assert delete_event["action"] == "DELETE"
    assert delete_event["entity_type"] == "CLIENT"
    assert delete_event["entity_id"] == client["id"]
    assert delete_event["user_name"] == "deleter"
    assert json.loads(delete_event["old_values"])["name"] == "Updated client"
    assert delete_event["new_values"] is None


def test_project_update_status_and_delete_capture_snapshots(temp_db):
    client = temp_db.add_client(
        {"name": "Project client", "email": "", "phone": ""},
        user_name="creator",
    )
    project = temp_db.add_project(
        {
            "name": "Original project",
            "client_id": client["id"],
            "status": "new",
            "budget": 100,
            "currency": "MAD",
        },
        user_name="creator",
    )

    updated = temp_db.update_project(
        project["id"],
        {
            "name": "Updated project",
            "client_id": client["id"],
            "status": "active",
            "budget": 250,
            "currency": "EUR",
        },
        user_name="editor",
    )
    update_event = temp_db.list_system_logs()[0]

    assert updated["name"] == "Updated project"
    assert update_event["action"] == "UPDATE"
    assert update_event["entity_type"] == "PROJECT"
    assert update_event["entity_id"] == project["id"]
    assert update_event["user_name"] == "editor"
    assert json.loads(update_event["old_values"])["budget"] == 100
    assert json.loads(update_event["new_values"])["budget"] == 250

    temp_db.set_project_status(project["id"], "done", user_name="manager")
    status_event = temp_db.list_system_logs()[0]

    assert status_event["action"] == "UPDATE"
    assert status_event["entity_type"] == "PROJECT"
    assert status_event["entity_id"] == project["id"]
    assert status_event["user_name"] == "manager"
    assert json.loads(status_event["old_values"]) == {"status": "active"}
    assert json.loads(status_event["new_values"]) == {"status": "done"}

    temp_db.delete_project(project["id"], user_name="deleter")
    delete_event = temp_db.list_system_logs()[0]

    assert delete_event["action"] == "DELETE"
    assert delete_event["entity_type"] == "PROJECT"
    assert delete_event["entity_id"] == project["id"]
    assert delete_event["user_name"] == "deleter"
    assert json.loads(delete_event["old_values"])["name"] == "Updated project"
    assert delete_event["new_values"] is None
