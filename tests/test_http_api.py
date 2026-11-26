"""Focused tests for HTTP request-body validation."""
import io
import unittest
from email.message import Message
from types import SimpleNamespace

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
