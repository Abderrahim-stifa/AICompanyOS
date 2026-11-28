"""Focused tests for HTTP request-body validation."""
import io
import json
import unittest
from email.message import Message
from types import SimpleNamespace
from unittest.mock import Mock

from cli import make_handler
from core.validator import ValidationError


class HttpBodyTests(unittest.TestCase):
    def setUp(self):
        company = SimpleNamespace(settings=SimpleNamespace(api_key=""))
        self.handler_type = make_handler(company)

    def read_body(self, length, body=b"{}"):
        handler = self.handler_type.__new__(self.handler_type)
        handler.headers = Message()
        handler.headers["Content-Length"] = length
        handler.rfile = io.BytesIO(body)
        return handler._read_json()

    def test_valid_object_body(self):
        self.assertEqual(self.read_body("7", b'{"a":1}'), {"a": 1})

    def test_rejects_invalid_content_length(self):
        for value in ("invalid", "-1"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.read_body(value)

    def test_rejects_invalid_utf8(self):
        with self.assertRaises(ValidationError):
            self.read_body("1", b"\xff")

    def test_rejects_non_object_json(self):
        with self.assertRaises(ValidationError):
            self.read_body("2", b"[]")


if __name__ == "__main__":
    unittest.main()


def _route(method, path, host="localhost", content_type=None, body=None):
    company = Mock()
    company.settings = SimpleNamespace(api_key="")
    handler_type = make_handler(company)
    handler = handler_type.__new__(handler_type)
    handler.headers = Message()
    handler.headers["Host"] = host
    if content_type:
        handler.headers["Content-Type"] = content_type
    if body is not None:
        encoded = json.dumps(body).encode("utf-8")
        handler.headers["Content-Length"] = str(len(encoded))
        handler.rfile = io.BytesIO(encoded)
    response = {}
    handler._send = lambda code, payload: response.update(code=code, payload=payload)
    handler.path = path
    handler._route(method)
    return response, company


def test_api_rejects_non_local_host_without_api_key():
    response, _ = _route("GET", "/health", host="attacker.example")
    assert response["code"] == 403


def test_api_rejects_write_without_json_content_type():
    response, _ = _route("POST", "/tasks", content_type="text/plain", body={})
    assert response["code"] == 415


def test_api_rejects_invalid_task_status_filter():
    response, company = _route("GET", "/tasks?status=not-a-status")
    assert response["code"] == 400
    company.db.list_tasks.assert_not_called()


def test_api_task_patch_uses_api_audit_actor():
    response, company = _route(
        "PATCH", "/tasks/7", content_type="application/json", body={"status": "done"}
    )
    company.update_task.assert_called_once_with(
        "7", {"status": "done"}, user_name="api"
    )


def test_cli_status_update_uses_cli_audit_actor(monkeypatch):
    import cli

    company = Mock()
    monkeypatch.setattr(cli, "Company", Mock(return_value=company))
    monkeypatch.setattr(cli, "show", Mock())
    assert cli.main(["set-status", "7", "done"]) == 0
    company.update_task.assert_called_once_with(
        "7", {"status": "done"}, user_name="cli"
    )


def test_api_lists_business_records_read_only():
    for path, method_name in (
        ("/clients", "list_clients"),
        ("/projects", "list_projects"),
        ("/invoices", "list_invoices"),
    ):
        response, company = _route("GET", path)
        assert response["code"] == 200
        getattr(company.db, method_name).assert_called_once_with()


def test_api_payments_filter_by_invoice_id():
    response, company = _route("GET", "/payments?invoice_id=12")
    assert response["code"] == 200
    company.db.list_payments.assert_called_once_with(12)
    response, company = _route("GET", "/payments")
    company.db.list_payments.assert_called_once_with(None)


def test_api_payments_rejects_non_numeric_invoice_id():
    response, company = _route("GET", "/payments?invoice_id=abc")
    assert response["code"] == 400
    company.db.list_payments.assert_not_called()


def test_api_business_records_have_no_write_routes():
    response, _ = _route(
        "POST", "/invoices", content_type="application/json", body={}
    )
    assert response["code"] == 404
