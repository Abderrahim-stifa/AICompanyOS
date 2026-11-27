"""Audited overdue invoice lifecycle regression tests."""
import json


def _task(db, title):
    return db.add_task({
        "title": title,
        "description": "",
        "source": "test",
        "category": "consulting",
        "price": 1000,
        "currency": "MAD",
        "priority": "normal",
    })


def _invoice(db, title, due_date, *, issue=True):
    invoice = db.create_invoice(_task(db, title)["id"], due_date=due_date)
    return db.issue_invoice(invoice["id"]) if issue else invoice


def test_overdue_transition_is_audited_and_idempotent(temp_db):
    overdue = _invoice(temp_db, "Past due", "2026-11-26")
    partial = _invoice(temp_db, "Partially paid past due", "2026-11-25")
    temp_db.record_payment(partial["id"], 200, "MAD", "2026-11-20")
    due_today = _invoice(temp_db, "Due today", "2026-11-27")
    future = _invoice(temp_db, "Future due", "2026-12-01")

    changed = temp_db.mark_overdue_invoices(today="2026-11-27", user_name="finance")
    assert {row["id"] for row in changed} == {overdue["id"], partial["id"]}
    states = {row["id"]: row["status"] for row in temp_db.list_invoices()}
    assert states[overdue["id"]] == "overdue"
    assert states[partial["id"]] == "overdue"
    assert states[due_today["id"]] == "issued"
    assert states[future["id"]] == "issued"

    events = [row for row in temp_db.list_system_logs()
              if row["entity_type"] == "INVOICE" and row["action"] == "OVERDUE"]
    assert len(events) == 2
    event = next(row for row in events if row["entity_id"] == overdue["id"])
    assert event["user_name"] == "finance"
    assert json.loads(event["old_values"])["status"] == "issued"
    assert json.loads(event["new_values"])["status"] == "overdue"

    assert temp_db.mark_overdue_invoices(today="2026-11-27", user_name="finance") == []
    assert len([row for row in temp_db.list_system_logs()
                if row["entity_type"] == "INVOICE" and row["action"] == "OVERDUE"]) == 2


def test_overdue_transition_excludes_draft_paid_and_void_invoices(temp_db):
    draft = _invoice(temp_db, "Draft", "2026-11-01", issue=False)
    paid = _invoice(temp_db, "Paid", "2026-11-01")
    temp_db.record_payment(paid["id"], 1000, "MAD", "2026-11-02")
    void = _invoice(temp_db, "Void", "2026-11-01")
    temp_db.void_invoice(void["id"], "Cancelled")

    changed = temp_db.mark_overdue_invoices(today="2026-11-27")
    assert changed == []
    states = {row["id"]: row["status"] for row in temp_db.list_invoices()}
    assert states[draft["id"]] == "draft"
    assert states[paid["id"]] == "paid"
    assert states[void["id"]] == "void"


def test_overdue_date_must_be_iso_formatted(temp_db):
    import pytest

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        temp_db.mark_overdue_invoices(today="27/11/2026")
