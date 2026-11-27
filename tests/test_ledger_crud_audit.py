"""Ledger update/delete audit regression tests."""
import json

import pytest


def _entry(temp_db):
    return temp_db.add_ledger_entry(
        {
            "task_id": None,
            "kind": "income",
            "amount": 125.50,
            "currency": "MAD",
            "note": "Initial receipt",
        },
        user_name="accountant",
    )


def test_update_ledger_entry_records_actor_and_before_after_snapshots(temp_db):
    entry = _entry(temp_db)

    updated = temp_db.update_ledger_entry(
        entry["id"],
        {
            "task_id": None,
            "kind": "expense",
            "amount": 75,
            "currency": "EUR",
            "note": "Corrected expense",
        },
        user_name="finance-operator",
    )

    event = temp_db.list_system_logs()[0]
    old_values = json.loads(event["old_values"])
    new_values = json.loads(event["new_values"])

    assert updated["kind"] == "expense"
    assert updated["amount"] == 75
    assert updated["created_at"] == entry["created_at"]
    assert event["action"] == "UPDATE"
    assert event["entity_type"] == "LEDGER"
    assert event["entity_id"] == entry["id"]
    assert event["user_name"] == "finance-operator"
    assert old_values["amount"] == 125.5
    assert old_values["note"] == "Initial receipt"
    assert new_values["amount"] == 75
    assert new_values["currency"] == "EUR"
    assert new_values["note"] == "Corrected expense"


def test_delete_ledger_entry_retains_snapshot_and_actor(temp_db):
    entry = _entry(temp_db)

    temp_db.delete_ledger_entry(entry["id"], user_name="finance-operator")

    assert temp_db.list_ledger() == []
    event = temp_db.list_system_logs()[0]
    assert event["action"] == "DELETE"
    assert event["entity_type"] == "LEDGER"
    assert event["entity_id"] == entry["id"]
    assert event["user_name"] == "finance-operator"
    assert json.loads(event["old_values"])["amount"] == 125.5
    assert json.loads(event["old_values"])["note"] == "Initial receipt"
    assert event["new_values"] is None


def test_ledger_update_rejects_missing_task_without_mutating_entry(temp_db):
    entry = _entry(temp_db)

    with pytest.raises(LookupError, match="task #999 not found"):
        temp_db.update_ledger_entry(
            entry["id"],
            {
                "task_id": 999,
                "kind": "income",
                "amount": 125.50,
                "currency": "MAD",
                "note": "Invalid reference",
            },
            user_name="finance-operator",
        )

    assert temp_db.list_ledger()[0]["note"] == "Initial receipt"
    assert temp_db.list_system_logs()[0]["action"] == "CREATE"


def test_ledger_update_and_delete_reject_missing_entry(temp_db):
    with pytest.raises(LookupError, match="ledger entry #999 not found"):
        temp_db.update_ledger_entry(
            999,
            {"task_id": None, "kind": "income", "amount": 1, "currency": "MAD", "note": ""},
        )

    with pytest.raises(LookupError, match="ledger entry #999 not found"):
        temp_db.delete_ledger_entry(999)
