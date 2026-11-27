"""Persistent invoice lifecycle and atomic payment regression tests."""
import json

import pytest


def _invoice(temp_db):
    task = temp_db.add_task({
        "title": "Website delivery",
        "description": "Final milestone",
        "source": "direct",
        "category": "development",
        "price": 1000,
        "currency": "MAD",
        "priority": "normal",
    })
    return temp_db.create_invoice(task["id"], due_date="2026-12-31",
                                  notes="Milestone invoice", user_name="finance")


def test_create_invoice_snapshots_task_and_starts_as_draft(temp_db):
    invoice = _invoice(temp_db)
    assert invoice["invoice_number"].startswith("INV-")
    assert invoice["task_title"] == "Website delivery"
    assert invoice["amount"] == 1000
    assert invoice["currency"] == "MAD"
    assert invoice["status"] == "draft"
    assert invoice["due_date"] == "2026-12-31"
    event = temp_db.list_system_logs()[0]
    assert event["entity_type"] == "INVOICE"
    assert json.loads(event["new_values"])["status"] == "draft"


def test_invoice_issue_is_audited_and_cannot_be_reissued(temp_db):
    invoice = _invoice(temp_db)
    issued = temp_db.issue_invoice(invoice["id"], user_name="operator")
    assert issued["status"] == "issued"
    assert issued["issue_date"]
    event = temp_db.list_system_logs()[0]
    assert event["action"] == "ISSUE"
    assert event["user_name"] == "operator"
    assert json.loads(event["old_values"])["status"] == "draft"
    with pytest.raises(ValueError, match="only draft invoices"):
        temp_db.issue_invoice(invoice["id"])


def test_partial_then_full_payment_updates_invoice_and_ledger_atomically(temp_db):
    invoice = temp_db.issue_invoice(_invoice(temp_db)["id"])
    first = temp_db.record_payment(
        invoice["id"], 300, "MAD", "2026-11-27", "bank_transfer",
        "TX-001", "Deposit", user_name="cashier",
    )
    current = temp_db.list_invoices()[0]
    assert current["status"] == "partially_paid"
    assert current["paid_amount"] == 300
    ledger = temp_db.list_ledger()
    assert len(ledger) == 1
    assert ledger[0]["kind"] == "income"
    assert ledger[0]["amount"] == 300
    assert first["ledger_id"] == ledger[0]["id"]

    temp_db.record_payment(
        invoice["id"], 700, "MAD", "2026-11-27", "cash",
        "TX-002", "Final payment",
    )
    current = temp_db.list_invoices()[0]
    assert current["status"] == "paid"
    assert current["paid_amount"] == 1000
    assert len(temp_db.list_ledger()) == 2
    assert len(temp_db.list_payments(invoice["id"])) == 2
    events = temp_db.list_system_logs()
    assert any(row["entity_type"] == "PAYMENT" and row["action"] == "CREATE"
               for row in events)
    assert any(row["entity_type"] == "INVOICE" and row["action"] == "PAYMENT_STATUS"
               for row in events)


def test_duplicate_payment_reference_and_overpayment_leave_no_partial_writes(temp_db):
    invoice = temp_db.issue_invoice(_invoice(temp_db)["id"])
    temp_db.record_payment(invoice["id"], 250, "MAD", "2026-11-27",
                           reference="UNIQUE-REF")
    before_logs = len(temp_db.list_system_logs())
    with pytest.raises(ValueError, match="reference already exists"):
        temp_db.record_payment(invoice["id"], 100, "MAD", "2026-11-27",
                               reference="UNIQUE-REF")
    with pytest.raises(ValueError, match="exceeds remaining balance"):
        temp_db.record_payment(invoice["id"], 800, "MAD", "2026-11-27")
    assert len(temp_db.list_payments(invoice["id"])) == 1
    assert len(temp_db.list_ledger()) == 1
    assert len(temp_db.list_system_logs()) == before_logs


def test_payment_requires_issued_invoice_and_matching_currency(temp_db):
    invoice = _invoice(temp_db)
    with pytest.raises(ValueError, match="only be recorded"):
        temp_db.record_payment(invoice["id"], 10, "MAD", "2026-11-27")
    temp_db.issue_invoice(invoice["id"])
    with pytest.raises(ValueError, match="currency must match"):
        temp_db.record_payment(invoice["id"], 10, "USD", "2026-11-27")
    assert temp_db.list_payments() == []
    assert temp_db.list_ledger() == []
