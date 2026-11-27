"""Arabic RTL HTML invoice generation with safe escaping and printable styling."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape
import math
from typing import Any


_STATUS_AR = {
    "found": "تم العثور",
    "classified": "مصنفة",
    "assigned": "مُسندة",
    "in_progress": "قيد التنفيذ",
    "done": "مكتملة",
    "rejected": "مرفوضة",
}


def _safe_text(value: Any, default: str = "") -> str:
    """Convert a value to text and escape it for an HTML text context."""
    if value is None:
        value = default
    return escape(str(value), quote=True)


def _format_price(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("price must be a finite non-negative number")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("price must be a finite non-negative number") from None
    if not amount.is_finite() or amount < 0:
        raise ValueError("price must be a finite non-negative number")
    return f"{amount:,.2f}"


def generate_invoice_html(
    task: dict, company_name: str, currency: str = "ر.س"
) -> str:
    """Generate an Arabic RTL invoice, ready for browser printing or PDF export.

    Dynamic values are HTML-escaped. The returned document is self-contained
    apart from the optional Google Fonts import, and uses the browser print
    dialog rather than a server-side PDF dependency.
    """
    if not isinstance(task, dict):
        raise TypeError("task must be a dictionary")

    date_str = datetime.now().strftime("%Y-%m-%d")
    task_id = _safe_text(task.get("id", "N/A"))
    title = _safe_text(task.get("title", "مهمة غير معنونة"))
    description = _safe_text(task.get("description", "لا يوجد وصف إضافي"))
    price = _format_price(task.get("price", 0.0))
    client_name = _safe_text(task.get("client_name", "عميل نقدي"))
    agent = _safe_text(task.get("agent", "غير محدد"))
    company = _safe_text(company_name, "AICompanyOS")
    currency_text = _safe_text(currency)
    raw_status = str(task.get("status", "غير محدد"))
    status = _safe_text(_STATUS_AR.get(raw_status, raw_status))

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>فاتورة مهمة #{task_id}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');
        * {{ box-sizing: border-box; }}
        body {{ font-family: 'Cairo', Tahoma, sans-serif; background: #f8fafc; color: #1e293b; padding: 20px; margin: 0; }}
        .invoice-box {{ max-width: 800px; margin: auto; background: #fff; padding: 40px; border-radius: 16px; box-shadow: 0 8px 30px rgba(0,0,0,.08); }}
        .header {{ display: flex; justify-content: space-between; align-items: center; gap: 20px; border-bottom: 3px solid #7c3aed; padding-bottom: 20px; margin-bottom: 30px; }}
        .company-name {{ font-size: 26px; font-weight: 800; color: #7c3aed; overflow-wrap: anywhere; }}
        .invoice-title {{ font-size: 18px; color: #64748b; font-weight: 600; }}
        .details {{ display: flex; justify-content: space-between; gap: 20px; margin-bottom: 30px; background: #f1f5f9; padding: 20px; border-radius: 12px; }}
        .details div {{ line-height: 2; }}
        .details strong {{ color: #334155; }}
        .items {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; }}
        .items th {{ background: #e2e8f0; padding: 14px; text-align: right; color: #475569; font-weight: 700; }}
        .items td {{ padding: 16px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
        .description {{ color: #64748b; font-size: 15px; line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }}
        .amount {{ text-align: left; direction: ltr; white-space: nowrap; font-weight: 700; font-size: 18px; }}
        .total {{ text-align: left; font-size: 24px; font-weight: 800; color: #7c3aed; margin-top: 20px; padding-top: 20px; border-top: 2px dashed #cbd5e1; }}
        .footer {{ text-align: center; margin-top: 50px; color: #94a3b8; font-size: 14px; line-height: 2; }}
        .btn-print {{ background: linear-gradient(135deg, #7c3aed, #db2777); color: white; border: 0; padding: 14px 32px; border-radius: 10px; font-family: 'Cairo', sans-serif; font-weight: 700; cursor: pointer; font-size: 16px; display: block; margin: 30px auto 0; }}
        @media (max-width: 600px) {{
            .invoice-box {{ padding: 20px; }}
            .header, .details {{ flex-direction: column; align-items: stretch; }}
            .details .status {{ text-align: right !important; }}
        }}
        @media print {{
            @page {{ size: A4; margin: 12mm; }}
            body {{ background: #fff; padding: 0; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
            .invoice-box {{ max-width: none; box-shadow: none; border-radius: 0; padding: 10px; }}
            .btn-print {{ display: none; }}
        }}
    </style>
</head>
<body>
    <main class="invoice-box">
        <header class="header">
            <div class="company-name">{company}</div>
            <div class="invoice-title">فاتورة / تقرير مهمة #{task_id}</div>
        </header>
        <section class="details">
            <div>
                <strong>العميل:</strong> {client_name}<br>
                <strong>التاريخ:</strong> {date_str}
            </div>
            <div class="status" style="text-align: left;">
                <strong>الحالة:</strong> {status}<br>
                <strong>الوكيل:</strong> {agent}
            </div>
        </section>
        <table class="items">
            <thead>
                <tr>
                    <th>وصف الخدمة / المهمة</th>
                    <th style="width: 180px; text-align: left;">المبلغ</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>
                        <strong style="font-size: 18px;">{title}</strong><br>
                        <span class="description">{description}</span>
                    </td>
                    <td class="amount">{price} {currency_text}</td>
                </tr>
            </tbody>
        </table>
        <div class="total">الإجمالي النهائي: {price} {currency_text}</div>
        <footer class="footer">
            تم إنشاء هذه الوثيقة إلكترونياً عبر نظام AICompanyOS<br>
            نشكركم على ثقتكم بنا
        </footer>
        <button class="btn-print" type="button" onclick="window.print()">طباعة أو حفظ كـ PDF</button>
    </main>
</body>
</html>
"""
