"""Tests for SQLite backup and restore safety."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.backup import create_backup, list_backups, restore_backup


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "data" / "company.db"
        self.db.parent.mkdir()
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE records (value TEXT NOT NULL)")
            conn.execute("INSERT INTO records VALUES ('original')")

    def tearDown(self):
        self.temp.cleanup()

    def test_backup_names_do_not_collide(self):
        backup_dir = self.root / "backups"
        first = create_backup(str(self.db), str(backup_dir))
        second = create_backup(str(self.db), str(backup_dir))
        self.assertNotEqual(first.name, second.name)
        self.assertEqual(len(list_backups(str(backup_dir))), 2)

    def test_backup_retention_keeps_newest(self):
        backup_dir = self.root / "backups"
        create_backup(str(self.db), str(backup_dir), keep=1)
        newest = create_backup(str(self.db), str(backup_dir), keep=1)
        self.assertEqual(list_backups(str(backup_dir)), [newest])

    def test_restore_preserves_pre_restore_database(self):
        backup = create_backup(str(self.db), str(self.root / "backups"))
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE records SET value = 'changed'")

        restore_backup(str(backup), str(self.db))

        with sqlite3.connect(self.db) as conn:
            restored = conn.execute("SELECT value FROM records").fetchone()[0]
        safety = self.db.with_name("company.before-restore.db")
        self.assertEqual(restored, "original")
        self.assertTrue(safety.exists())
        with sqlite3.connect(safety) as conn:
            preserved = conn.execute("SELECT value FROM records").fetchone()[0]
        self.assertEqual(preserved, "changed")

    def test_restore_creates_missing_target_directory(self):
        backup = create_backup(str(self.db), str(self.root / "backups"))
        target = self.root / "new" / "nested" / "restored.db"
        restore_backup(str(backup), str(target))
        self.assertTrue(target.exists())


if __name__ == "__main__":
    unittest.main()
