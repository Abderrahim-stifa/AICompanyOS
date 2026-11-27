"""Tests for SQLite database maintenance operations."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.database import Database


class DatabaseVacuumTests(unittest.TestCase):
    def test_vacuum_preserves_data_and_database_integrity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "company.db"
            db = Database(str(db_path))
            db.init()

            with db.connect() as conn:
                conn.execute("CREATE TABLE vacuum_test (value TEXT NOT NULL)")
                conn.executemany(
                    "INSERT INTO vacuum_test (value) VALUES (?)",
                    [(f"record-{index}",) for index in range(100)],
                )
                conn.execute("DELETE FROM vacuum_test WHERE value LIKE 'record-%'")

            db.vacuum()

            with sqlite3.connect(db_path) as conn:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                count = conn.execute("SELECT COUNT(*) FROM vacuum_test").fetchone()[0]

            self.assertEqual(integrity, "ok")
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
