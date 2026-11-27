"""Tests for safe Arabic HTML invoice generation."""
import unittest

from core.invoice import generate_invoice_html


class InvoiceHtmlTests(unittest.TestCase):
    def test_generates_arabic_rtl_printable_invoice(self):
        html = generate_invoice_html(
            {
                "id": 17,
                "title": "تصميم موقع",
                "description": "تصميم وتطوير صفحة رئيسية",
                "price": 1250.5,
                "client_name": "شركة الاختبار",
                "status": "done",
                "agent": "engineer",
            },
            "AICompanyOS",
            "MAD",
        )
        self.assertIn('<html dir="rtl" lang="ar">', html)
        self.assertIn("شركة الاختبار", html)
        self.assertIn("1,250.50 MAD", html)
        self.assertIn("مكتملة", html)
        self.assertIn("window.print()", html)
        self.assertIn("@media print", html)

    def test_escapes_untrusted_dynamic_values(self):
        html = generate_invoice_html(
            {
                "id": '"><script>alert(1)</script>',
                "title": '<img src=x onerror="alert(1)">',
                "description": "<script>bad()</script>",
                "price": 10,
                "client_name": "<svg onload=alert(1)>",
                "status": "custom<script>",
                "agent": "<b>agent</b>",
            },
            '<iframe src="evil"></iframe>',
            "<script>",
        )
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<svg", html)
        self.assertNotIn("<iframe", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)

    def test_defaults_missing_optional_fields(self):
        html = generate_invoice_html({}, "الشركة")
        self.assertIn("مهمة غير معنونة", html)
        self.assertIn("عميل نقدي", html)
        self.assertIn("0.00", html)

    def test_rejects_invalid_or_negative_price(self):
        for value in (-1, "NaN", "Infinity", "not-a-price", True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    generate_invoice_html({"price": value}, "الشركة")

    def test_rejects_non_dictionary_task(self):
        with self.assertRaises(TypeError):
            generate_invoice_html([], "الشركة")


if __name__ == "__main__":
    unittest.main()
