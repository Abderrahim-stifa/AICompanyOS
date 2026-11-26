"""Isolated tests for persisted UI settings."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core import init_db


class SettingsTests(unittest.TestCase):
    def test_settings_round_trip_and_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "company.db")
            settings_path = Path(directory) / "settings.json"
            with patch.object(init_db, "SETTINGS_FILE", settings_path):
                init_db.initialize_database(db_path)
                saved = init_db.save_ui_settings({
                    "company_name": "شركة الاختبار",
                    "language": "ar",
                    "dark_mode": False,
                    "theme": "modern",
                }, db_path)
                loaded = init_db.load_ui_settings(db_path)

            self.assertEqual(saved, loaded)
            self.assertEqual(loaded["company_name"], "شركة الاختبار")
            self.assertIs(loaded["dark_mode"], False)
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(("company_name", "language", "dark_mode", "theme")) - set(data),
                set(),
            )

    def test_invalid_settings_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "company.db")
            settings_path = Path(directory) / "settings.json"
            with patch.object(init_db, "SETTINGS_FILE", settings_path):
                init_db.initialize_database(db_path)
                with self.assertRaises(ValueError):
                    init_db.save_ui_settings({"company_name": " "}, db_path)
                with self.assertRaises(ValueError):
                    init_db.save_ui_settings({"language": "fr"}, db_path)


if __name__ == "__main__":
    unittest.main()
