"""Invoice voiding, payment refunds, and ledger-integrity regression tests."""
import json

import pytest


def _issued_invoice(db, amount=1000):
    task = db.add_task({
        "title": "Consulting milestone",
        "description": "Delivery",
        "source": "test",
        "category": "consulting",
        "price": amount,
        "currency": "MAD",
        "priority": "normal",
    })
    invoice = db.create_invoice(task["id"], user_name="finance")
    return db.issue_invoice(invoice["id"], user_name="finance")


def test_void_unpaid_invoice_is_audited_and_rejects_payment(temp_db):
    invoice = temp_db.create_invoice(
        temp_db.add_task({
            "title": "Unpaid work", "description": "", "source": "test",
            "category": "test", "price": 500, "currency": "MAD",
            "priority": "normal",
        })["id"],
        user_name="operator",
    )
    voided = temp_db.void_invoice(invoice["id"], "Client cancelled", "operator")
    assert voided["status"] == "void"
    event = temp_db.list_system_logs()[0]
    assert event["action"] == "VOID"
    assert event["user_name"] == "operator"
    assert "Client cancelled" in json.loads(event["new_values"])["notes"]
    with pytest.raises(ValueError, match="only be recorded"):
        temp_db.record_payment(invoice["id"], 10, "MAD", "2026-11-27")


def test_invoice_with_payments_cannot_be_voided(temp_db):
    invoice = _issued_invoice(temp_db)
    temp_db.record_payment(invoice["id"], 100, "MAD", "2026-11-27")
    with pytest.raises(ValueError, match="payments cannot be voided"):
        temp_db.void_invoice(invoice["id"], "Cancel")
    assert temp_db.list_invoices()[0]["status"] == "partially_paid"


def test_partial_refund_creates_expense_and_recalculates_invoice_balance(temp_db):
    invoice = _issued_invoice(temp_db)
    payment = temp_db.record_payment(
        invoice["id"], 800, "MAD", "2026-11-27", reference="PAY-REFUND-1"
    )
    refund = temp_db.refund_payment(
        payment["id"], 300, "2026-11-27", "REF-001", "Partial refund",
        user_name="cashier",
    )
    assert refund["amount"] == 300
    current = temp_db.list_invoices()[0]
    assert current["paid_amount"] == 800
    assert current["refunded_amount"] == 300
    assert current["net_paid_amount"] == 500
    assert current["status"] == "partially_paid"
    ledger = temp_db.list_ledger()
    assert len(ledger) == 2
    assert sorted(row["kind"] for row in ledger) == ["expense", "income"]
    assert next(row for row in ledger if row["kind"] == "expense")["amount"] == 300
    assert any(row["entity_type"] == "REFUND" and row["action"] == "CREATE"
               for row in temp_db.list_system_logs())


def test_full_refund_reopens_invoice_and_prevents_over_refund(temp_db):
    invoice = _issued_invoice(temp_db)
    payment = temp_db.record_payment(invoice["id"], 1000, "MAD", "2026-11-27")
    temp_db.refund_payment(payment["id"], 1000, "2026-11-27")
    current = temp_db.list_invoices()[0]
    assert current["net_paid_amount"] == 0
    assert current["status"] == "issued"
    with pytest.raises(ValueError, match="exceeds refundable payment balance"):
        temp_db.refund_payment(payment["id"], 0.01, "2026-11-27")
    assert len(temp_db.list_refunds()) == 1
    assert len(temp_db.list_ledger()) == 2


def test_duplicate_refund_reference_rolls_back_and_linked_ledger_is_protected(temp_db):
    invoice = _issued_invoice(temp_db)
    payment = temp_db.record_payment(invoice["id"], 500, "MAD", "2026-11-27")
    refund = temp_db.refund_payment(
        payment["id"], 100, "2026-11-27", reference="REF-UNIQUE"
    )
    before = len(temp_db.list_system_logs())
    with pytest.raises(ValueError, match="reference already exists"):
        temp_db.refund_payment(
            payment["id"], 50, "2026-11-27", reference="REF-UNIQUE"
        )
    with pytest.raises(ValueError, match="cannot be edited"):
        temp_db.update_ledger_entry(
            refund["ledger_id"],
            {"task_id": None, "kind": "income", "amount": 100,
             "currency": "MAD", "note": "corrupted"},
        )
    with pytest.raises(ValueError, match="cannot be deleted"):
        temp_db.delete_ledger_entry(refund["ledger_id"])
    assert len(temp_db.list_refunds()) == 1
    assert len(temp_db.list_ledger()) == 2
    assert len(temp_db.list_system_logs()) == before


def test_refund_amount_must_not_exceed_original_payment(temp_db):
    invoice = _issued_invoice(temp_db)
    payment = temp_db.record_payment(invoice["id"], 200, "MAD", "2026-11-27")
    with pytest.raises(ValueError, match="exceeds refundable payment balance"):
        temp_db.refund_payment(payment["id"], 201, "2026-11-27")
    assert temp_db.list_refunds() == []
    assert len(temp_db.list_ledger()) == 1
