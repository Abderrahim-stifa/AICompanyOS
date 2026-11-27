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



def test_client_project_and_ledger_audits_capture_actor_and_snapshots(temp_db):
    client = temp_db.add_client(
        {"name": "Audit client", "email": "", "phone": ""}, user_name="operator"
    )
    project = temp_db.add_project({
        "name": "Audit project", "client_id": client["id"], "status": "new",
        "budget": 100, "currency": "MAD",
    }, user_name="operator")
    temp_db.add_ledger_entry({
        "task_id": None, "kind": "income", "amount": 25,
        "currency": "MAD", "note": "Test income",
    }, user_name="accountant")

    events = temp_db.list_system_logs()
    assert [event["entity_type"] for event in events[:3]] == [
        "LEDGER", "PROJECT", "CLIENT"
    ]
    assert all(event["user_name"] == "operator" for event in events[1:])
    assert events[0]["user_name"] == "accountant"
    assert json.loads(events[0]["new_values"])["amount"] == 25
    assert json.loads(events[1]["new_values"])["name"] == "Audit project"
    assert json.loads(events[2]["new_values"])["name"] == "Audit client"
