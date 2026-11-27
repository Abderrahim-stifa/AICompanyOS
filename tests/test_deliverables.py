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
        self.assertEqual(len(self.store.versions(item["id"])),1)

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
