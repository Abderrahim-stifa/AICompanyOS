"""Input validation. All functions return cleaned values or raise ValidationError."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

import re

TASK_STATUSES = ("found", "classified", "assigned", "in_progress", "done", "rejected")
PROJECT_STATUSES = ("new", "in_progress", "done", "on_hold")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
LEDGER_KINDS = ("income", "expense")
CURRENCIES = ("USD", "EUR", "MAD", "SAR", "AED", "EGP")


class ValidationError(ValueError):
    """Raised when user input is invalid."""


def clean_text(value, field: str, *, required: bool = True, max_len: int = 500) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{field} is required")
    if len(value) > max_len:
        raise ValidationError(f"{field} is too long (max {max_len} characters)")
    return value


def clean_choice(value, field: str, choices: tuple[str, ...]) -> str:
    value = clean_text(value, field, max_len=50).lower()
    if value not in choices:
        raise ValidationError(f"{field} must be one of: {', '.join(choices)}")
    return value


def clean_currency(value, field: str = "currency") -> str:
    value = clean_text(value, field, max_len=3).upper()
    if value not in CURRENCIES:
        raise ValidationError(f"{field} must be one of: {', '.join(CURRENCIES)}")
    return value


def clean_amount(value, field: str = "amount", *, allow_zero: bool = True) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a number")
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError):
        raise ValidationError(f"{field} must be a number") from None
    if not amount.is_finite():
        raise ValidationError(f"{field} must be a finite number")
    if amount < 0 or (amount == 0 and not allow_zero):
        raise ValidationError(f"{field} must be {'positive' if not allow_zero else 'zero or more'}")
    return float(round(amount, 2))


def clean_id(value, field: str = "id") -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be an integer") from None
    if number < 1:
        raise ValidationError(f"{field} must be positive")
    return number


def clean_email(value, field: str = "email") -> str:
    value = clean_text(value, field, required=False, max_len=200)
    if value and not _EMAIL_RE.match(value):
        raise ValidationError(f"{field} is not a valid email address")
    return value


def validate_client(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("client must be an object")
    return {
        "name": clean_text(data.get("name"), "name", max_len=150),
        "email": clean_email(data.get("email")),
        "phone": clean_text(data.get("phone"), "phone", required=False, max_len=30),
    }


def validate_project(data: dict, default_currency: str = "USD") -> dict:
    if not isinstance(data, dict):
        raise ValidationError("project must be an object")
    client_id = data.get("client_id")
    return {
        "name": clean_text(data.get("name"), "name", max_len=200),
        "client_id": clean_id(client_id, "client_id") if client_id not in (None, "") else None,
        "status": clean_choice(data.get("status") or "new", "status", PROJECT_STATUSES),
        "budget": clean_amount(data.get("budget", 0), "budget"),
        "currency": clean_currency(data.get("currency") or default_currency),
    }


def validate_task(data: dict, default_currency: str = "USD") -> dict:
    if not isinstance(data, dict):
        raise ValidationError("task must be an object")
    return {
        "title": clean_text(data.get("title"), "title", max_len=200),
        "description": clean_text(data.get("description"), "description", required=False, max_len=5000),
        "source": clean_text(data.get("source"), "source", required=False, max_len=200),
        "category": clean_text(data.get("category"), "category", required=False, max_len=100),
        "price": clean_amount(data.get("price", 0), "price"),
        "currency": clean_currency(data.get("currency") or default_currency),
        "priority": clean_choice(data.get("priority") or "normal", "priority", ("low", "normal", "high", "urgent")),
    }


def validate_ledger_entry(data: dict, default_currency: str = "USD") -> dict:
    if not isinstance(data, dict):
        raise ValidationError("entry must be an object")
    task_id = data.get("task_id")
    return {
        "kind": clean_choice(data.get("kind"), "kind", LEDGER_KINDS),
        "amount": clean_amount(data.get("amount"), "amount", allow_zero=False),
        "currency": clean_currency(data.get("currency") or default_currency),
        "note": clean_text(data.get("note"), "note", required=False, max_len=500),
        "task_id": clean_id(task_id, "task_id") if task_id not in (None, "") else None,
    }
