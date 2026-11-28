"""Capture representative, authenticated UI screenshots using disposable demo data.

The script is used only by GitHub Actions. It never reads production credentials or data.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from core.service import Company


BASE_URL = "http://127.0.0.1:8501"
OUTPUT_DIR = Path("docs/screenshots")


def seed_demo_data() -> None:
    """Create synthetic records in the isolated CI database."""
    company = Company()
    client = company.add_client(
        {
            "name": "شركة الأطلس التجريبية",
            "email": "demo@example.invalid",
            "phone": "+212600000000",
        },
        user_name="screenshot-demo",
    )
    project = company.add_project(
        {
            "name": "منصة التجارة الرقمية",
            "client_id": client["id"],
            "status": "in_progress",
            "budget": 42000,
            "currency": "MAD",
        },
        user_name="screenshot-demo",
    )

    examples = (
        ("تصميم تجربة المستخدم للمنصة", "design", "in_progress", 8500),
        ("تطوير لوحة تحكم العملاء", "development", "classified", 12000),
        ("إعداد دراسة السوق الأولية", "research", "done", 3500),
        ("اختبار واجهة الدفع", "testing", "found", 2200),
    )
    for title, category, status, price in examples:
        task = company.add_task(
            {
                "title": title,
                "description": "مهمة توضيحية ببيانات اصطناعية لصور واجهة المشروع.",
                "source": "demo",
                "category": category,
                "price": price,
                "currency": "MAD",
                "priority": "high" if status == "in_progress" else "normal",
                "client_id": client["id"],
                "project_id": project["id"],
            },
            user_name="screenshot-demo",
        )
        company.set_task_status(task["id"], status)

    company.add_ledger(
        {
            "kind": "income",
            "amount": 8500,
            "currency": "MAD",
            "note": "قيد دخل تجريبي للعرض فقط",
        },
        user_name="screenshot-demo",
    )
    company.add_ledger(
        {
            "kind": "expense",
            "amount": 1200,
            "currency": "MAD",
            "note": "قيد مصروف تجريبي للعرض فقط",
        },
        user_name="screenshot-demo",
    )


def wait_for_server(process: subprocess.Popen) -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Streamlit exited before screenshot capture")
        try:
            with urlopen(f"{BASE_URL}/_stcore/health", timeout=2) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError("Streamlit did not become ready for screenshot capture")


def main() -> None:
    if not os.environ.get("AICOS_AUTH_USERNAME") or not os.environ.get("AICOS_AUTH_PASSWORD"):
        raise RuntimeError("CI-only screenshot login credentials are not configured")

    seed_demo_data()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
            "--server.port",
            "8501",
            "--browser.gatherUsageStats",
            "false",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_server(process)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(
                viewport={"width": 1600, "height": 1100},
                device_scale_factor=1,
            )
            page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            page.get_by_label("اسم المستخدم").wait_for(timeout=30000)
            page.get_by_label("اسم المستخدم").fill(os.environ["AICOS_AUTH_USERNAME"])
            page.get_by_label("كلمة المرور").fill(os.environ["AICOS_AUTH_PASSWORD"])
            page.get_by_role("button", name="دخول").click()
            page.get_by_role("heading", name="لوحة التحكم").wait_for(timeout=45000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUTPUT_DIR / "dashboard.png"), full_page=True)

            for label, filename in (
                ("المهام", "tasks.png"),
                ("العملاء", "clients.png"),
                ("المشاريع", "projects.png"),
            ):
                page.get_by_role("link", name=label).click(timeout=15000)
                page.wait_for_timeout(1200)
                page.screenshot(path=str(OUTPUT_DIR / filename), full_page=True)

            browser.close()
        print(f"Captured authenticated demo screenshots in {OUTPUT_DIR}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    main()
