"""Audit trail snapshot regression tests."""
import json


def test_update_log_contains_old_and_new_values(temp_db, sample_task):
    before = temp_db.get_task(sample_task["id"])
    after = temp_db.update_task(
        sample_task["id"], title="Updated Sample", description="Changed description",
        user_name="Auditor",
    )

    event = temp_db.list_system_logs()[0]
    old_values = json.loads(event["old_values"])
    new_values = json.loads(event["new_values"])

    assert before["title"] == old_values["title"] == "Sample Task"
    assert after["title"] == new_values["title"] == "Updated Sample"
    assert old_values["description"] == "Fixture task"
    assert new_values["description"] == "Changed description"
    assert event["user_name"] == "Auditor"



def test_create_log_contains_created_snapshot(temp_db):
    created = temp_db.add_task({
        "title": "Audit create", "description": "Initial",
        "source": "test", "category": "", "price": 0,
        "currency": "MAD",
    })
    event = temp_db.list_system_logs()[0]
    assert event["old_values"] is None
    assert json.loads(event["new_values"])["id"] == created["id"]
    assert json.loads(event["new_values"])["title"] == "Audit create"

def test_delete_log_keeps_deleted_snapshot(temp_db, sample_task):
    temp_db.delete_task(sample_task["id"], user_name="Owner")
    event = temp_db.list_system_logs()[0]

    assert event["action"] == "DELETE"
    assert json.loads(event["old_values"])["title"] == "Sample Task"
    assert event["new_values"] is None
