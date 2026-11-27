"""Tests for project-linked deliverables, immutable versions, and review controls."""
import os
import tempfile
import unittest

from core.database import Database
from core.deliverables import DeliverableStore
from core.validator import ValidationError


class DeliverableStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self.tmp.name, "test.sqlite"))
        self.db.init()
        with self.db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO projects(name,status,budget,currency,created_at) VALUES(?,?,?,?,?)",
                ("Project Alpha","new",0,"USD","2026-01-01T00:00:00+00:00"),
            )
            self.project_id = cur.lastrowid
        self.store = DeliverableStore(self.db)
        self.store.init()

    def tearDown(self):
        self.tmp.cleanup()

    def create_item(self):
        return self.store.create(
            self.project_id,"software","Requirements",
            "Initial requirements document","owner-a",
            ["https://example.test/spec"],["Assume 3 user roles"],
        )

    def test_create_requires_existing_project_and_saves_version_one(self):
        item = self.create_item()
        self.assertEqual(item["version"],1)
        self.assertEqual(item["status"],"draft")
        self.assertEqual(item["project_id"],self.project_id)
        self.assertEqual(item["generation_metadata"],{})
        self.assertEqual(len(self.store.versions(item["id"])),1)

    def test_generation_provenance_is_persisted_on_record_and_immutable_version(self):
        metadata = {
            "provider": "openai",
            "model": "test-model",
            "mode": "LLM",
            "verification": "not_verified",
            "approved": False,
            "execution_performed": False,
        }
        item = self.store.create(
            self.project_id,"software","Draft","Generated draft","owner-a",
            [],["Assumption"],metadata,
        )
        self.assertEqual(item["generation_metadata"],metadata)
        version = self.store.versions(item["id"])[0]
        self.assertEqual(version["generation_metadata"],metadata)

        revised_metadata = {"provider":"offline","model":"rules-v1","verification":"not_verified"}
        revised = self.store.revise(
            item["id"],"Draft v2","Revised content","owner-b",[],[],revised_metadata
        )
        versions = self.store.versions(item["id"])
        self.assertEqual(revised["generation_metadata"],revised_metadata)
        self.assertEqual(versions[0]["generation_metadata"],revised_metadata)
        self.assertEqual(versions[1]["generation_metadata"],metadata)

    def test_invalid_generation_metadata_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.store.create(
                self.project_id,"software","Draft","Content","owner",
                generation_metadata={"bad": object()},
            )
        with self.assertRaises(ValidationError):
            self.store.create(
                self.project_id,"software","Draft","Content","owner",
                generation_metadata={"large":"x" * 5000},
            )

    def test_legacy_deliverable_tables_receive_additive_metadata_migration(self):
        legacy_db = Database(os.path.join(self.tmp.name, "legacy.sqlite"))
        legacy_db.init()
        with legacy_db.connect() as conn:
            conn.execute("""
                CREATE TABLE deliverables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
                    domain TEXT NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    assumptions_json TEXT NOT NULL DEFAULT '[]',
                    owner TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
                    version INTEGER NOT NULL DEFAULT 1, reviewer TEXT,
                    review_note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE deliverable_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deliverable_id INTEGER NOT NULL REFERENCES deliverables(id) ON DELETE CASCADE,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
                    version INTEGER NOT NULL, title TEXT NOT NULL, content TEXT NOT NULL,
                    sources_json TEXT NOT NULL, assumptions_json TEXT NOT NULL,
                    owner TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(deliverable_id, version)
                )
            """)
        legacy_store = DeliverableStore(legacy_db)
        legacy_store.init()
        with legacy_db.connect() as conn:
            for table in ("deliverables","deliverable_versions"):
                columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
                self.assertIn("generation_metadata_json",columns)

    def test_unknown_project_is_rejected(self):
        with self.assertRaises(LookupError):
            self.store.create(9999,"design","Mockup","Draft","owner")

    def test_revisions_are_immutable_snapshots_and_reset_review(self):
        item = self.create_item()
        self.store.set_status(item["id"],"in_review","reviewer")
        self.store.set_status(item["id"],"approved","reviewer","Looks good")
        revised = self.store.revise(
            item["id"],"Requirements v2","Updated content","owner-b",
            ["source-v2"],["new assumption"],
        )
        self.assertEqual(revised["version"],2)
        self.assertEqual(revised["status"],"draft")
        versions = self.store.versions(item["id"])
        self.assertEqual([v["version"] for v in versions],[2,1])
        self.assertEqual(versions[1]["content"],"Initial requirements document")
        self.assertEqual(versions[0]["owner"],"owner-b")
        self.assertEqual(versions[0]["project_id"],self.project_id)
        self.assertEqual(versions[1]["project_id"],self.project_id)

    def test_approval_requires_review_state(self):
        item = self.create_item()
        with self.assertRaises(ValidationError):
            self.store.set_status(item["id"],"approved","reviewer")
        self.store.set_status(item["id"],"in_review","reviewer")
        approved = self.store.set_status(item["id"],"approved","reviewer","Checked")
        self.assertEqual(approved["status"],"approved")
        self.assertEqual(approved["reviewer"],"reviewer")

    def test_invalid_domain_and_empty_content_rejected(self):
        with self.assertRaises(ValidationError):
            self.store.create(self.project_id,"unknown","Title","Content","owner")
        with self.assertRaises(ValidationError):
            self.store.create(self.project_id,"design","Title"," ","owner")

    def test_project_delete_is_restricted_while_deliverables_exist(self):
        self.create_item()
        with self.assertRaises(Exception):
            self.db.delete_project(self.project_id,user_name="tester")

    def test_audit_events_record_create_revision_and_review(self):
        item = self.create_item()
        self.store.set_status(item["id"],"in_review","reviewer")
        self.store.set_status(item["id"],"rejected","reviewer","Needs evidence")
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT action FROM activity_logs WHERE entity_type='DELIVERABLE' ORDER BY id"
            ).fetchall()
        self.assertEqual([r["action"] for r in rows],[
            "DELIVERABLE_CREATED","DELIVERABLE_IN_REVIEW","DELIVERABLE_REJECTED"
        ])


if __name__ == "__main__":
    unittest.main()
