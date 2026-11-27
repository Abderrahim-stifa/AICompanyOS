"""Versioned, project-linked domain deliverables with explicit review state."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from core.database import Database
from core.validator import ValidationError

DOMAINS = {
    "software": "هندسة وتطوير البرمجيات",
    "design": "التصميم والهوية البصرية",
    "architecture": "التصورات المعمارية",
    "feasibility": "دراسة الجدوى",
}
STATUSES = ("draft", "in_review", "approved", "rejected")
MAX_TEXT = 20000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _required_text(value: Any, label: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} مطلوب.")
    value = value.strip()
    if len(value) > limit:
        raise ValidationError(f"{label} تجاوز الحد الأقصى ({limit} حرف).")
    return value


class DeliverableStore:
    """Persists project deliverables, immutable snapshots, and review audit events."""

    def __init__(self, db: Database):
        self.db = db

    def init(self) -> None:
        with self.db.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deliverables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
                    domain TEXT NOT NULL CHECK(domain IN ('software','design','architecture','feasibility')),
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources_json TEXT NOT NULL DEFAULT '[]',
                    assumptions_json TEXT NOT NULL DEFAULT '[]',
                    owner TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'draft'
                        CHECK(status IN ('draft','in_review','approved','rejected')),
                    version INTEGER NOT NULL DEFAULT 1,
                    reviewer TEXT,
                    review_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS deliverable_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deliverable_id INTEGER NOT NULL REFERENCES deliverables(id) ON DELETE CASCADE,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
                    version INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    assumptions_json TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(deliverable_id, version)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_deliverables_project ON deliverables(project_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_deliverables_domain ON deliverables(domain)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_deliverable_versions_parent ON deliverable_versions(deliverable_id, version)")

    @staticmethod
    def _decode(row: sqlite3.Row | dict) -> dict:
        item = dict(row)
        item["sources"] = json.loads(item.pop("sources_json"))
        item["assumptions"] = json.loads(item.pop("assumptions_json"))
        return item

    @staticmethod
    def _audit(conn, action: str, deliverable_id: int, user: str, details: str) -> None:
        conn.execute(
            """INSERT INTO activity_logs
               (action, entity_type, entity_id, user_name, details, created_at)
               VALUES (?, 'DELIVERABLE', ?, ?, ?, ?)""",
            (action, deliverable_id, user, details, _now()),
        )

    def create(self, project_id: int, domain: str, title: str, content: str,
               owner: str, sources: list[str] | None = None,
               assumptions: list[str] | None = None) -> dict:
        if domain not in DOMAINS:
            raise ValidationError("مجال المخرج غير صالح.")
        title = _required_text(title, "العنوان", 200)
        content = _required_text(content, "المحتوى")
        owner = _required_text(owner, "المسؤول", 100)
        sources = self._clean_list(sources, "المصادر")
        assumptions = self._clean_list(assumptions, "الافتراضات")
        now = _now()
        with self.db.connect(immediate=True) as conn:
            if conn.execute("SELECT 1 FROM projects WHERE id=?", (project_id,)).fetchone() is None:
                raise LookupError(f"project #{project_id} not found")
            cur = conn.execute(
                """INSERT INTO deliverables
                   (project_id,domain,title,content,sources_json,assumptions_json,owner,
                    status,version,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,'draft',1,?,?)""",
                (project_id,domain,title,content,json.dumps(sources,ensure_ascii=False),
                 json.dumps(assumptions,ensure_ascii=False),owner,now,now),
            )
            did = cur.lastrowid
            conn.execute(
                """INSERT INTO deliverable_versions
                   (deliverable_id,project_id,version,title,content,sources_json,assumptions_json,owner,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (did,project_id,1,title,content,json.dumps(sources,ensure_ascii=False),
                 json.dumps(assumptions,ensure_ascii=False),owner,now),
            )
            self._audit(conn,"DELIVERABLE_CREATED",did,owner,f"project={project_id}; domain={domain}; version=1")
        return self.get(did)

    @staticmethod
    def _clean_list(values: list[str] | None, label: str) -> list[str]:
        if values is None:
            return []
        if not isinstance(values, list) or len(values) > 50:
            raise ValidationError(f"قائمة {label} غير صالحة.")
        cleaned = []
        for value in values:
            cleaned.append(_required_text(value, label, 1000))
        return cleaned

    def revise(self, deliverable_id: int, title: str, content: str, owner: str,
               sources: list[str] | None = None,
               assumptions: list[str] | None = None) -> dict:
        title = _required_text(title, "العنوان", 200)
        content = _required_text(content, "المحتوى")
        owner = _required_text(owner, "المسؤول", 100)
        sources = self._clean_list(sources, "المصادر")
        assumptions = self._clean_list(assumptions, "الافتراضات")
        now = _now()
        with self.db.connect(immediate=True) as conn:
            row = conn.execute("SELECT * FROM deliverables WHERE id=?", (deliverable_id,)).fetchone()
            if row is None:
                raise LookupError(f"deliverable #{deliverable_id} not found")
            version = row["version"] + 1
            source_json = json.dumps(sources,ensure_ascii=False)
            assumptions_json = json.dumps(assumptions,ensure_ascii=False)
            conn.execute(
                """UPDATE deliverables SET title=?,content=?,sources_json=?,assumptions_json=?,
                   owner=?,status='draft',version=?,reviewer=NULL,review_note='',updated_at=?
                   WHERE id=?""",
                (title,content,source_json,assumptions_json,owner,version,now,deliverable_id),
            )
            conn.execute(
                """INSERT INTO deliverable_versions
                   (deliverable_id,project_id,version,title,content,sources_json,assumptions_json,owner,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (deliverable_id,row["project_id"],version,title,content,source_json,assumptions_json,owner,now),
            )
            self._audit(conn,"DELIVERABLE_REVISED",deliverable_id,owner,f"version={version}; review reset to draft")
        return self.get(deliverable_id)

    def set_status(self, deliverable_id: int, status: str, reviewer: str, note: str = "") -> dict:
        if status not in {"in_review","approved","rejected"}:
            raise ValidationError("حالة المراجعة غير صالحة.")
        reviewer = _required_text(reviewer,"المراجع",100)
        note = (note or "").strip()
        if len(note) > 2000:
            raise ValidationError("ملاحظة المراجعة طويلة جداً.")
        with self.db.connect(immediate=True) as conn:
            row = conn.execute("SELECT * FROM deliverables WHERE id=?", (deliverable_id,)).fetchone()
            if row is None:
                raise LookupError(f"deliverable #{deliverable_id} not found")
            if status in {"approved","rejected"} and row["status"] != "in_review":
                raise ValidationError("يجب إرسال الإصدار للمراجعة قبل اعتماده أو رفضه.")
            conn.execute(
                """UPDATE deliverables SET status=?,reviewer=?,review_note=?,updated_at=?
                   WHERE id=?""",
                (status,reviewer,note,_now(),deliverable_id),
            )
            self._audit(conn,f"DELIVERABLE_{status.upper()}",deliverable_id,reviewer,
                        f"version={row['version']}; note={note}")
        return self.get(deliverable_id)

    def get(self, deliverable_id: int) -> dict:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM deliverables WHERE id=?", (deliverable_id,)).fetchone()
        if row is None:
            raise LookupError(f"deliverable #{deliverable_id} not found")
        return self._decode(row)

    def list(self, project_id: int | None = None) -> list[dict]:
        query = "SELECT * FROM deliverables"
        params: tuple = ()
        if project_id is not None:
            query += " WHERE project_id=?"
            params = (project_id,)
        query += " ORDER BY updated_at DESC, id DESC"
        with self.db.connect() as conn:
            rows = conn.execute(query,params).fetchall()
        return [self._decode(row) for row in rows]

    def versions(self, deliverable_id: int) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM deliverable_versions WHERE deliverable_id=? ORDER BY version DESC",
                (deliverable_id,),
            ).fetchall()
        return [dict(row) for row in rows]
