"""SQLite storage for tasks, agents and the accounting ledger."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .logs import get_logger
from .validator import TASK_STATUSES, ValidationError

log = get_logger("database")
_UNSET = object()

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT '',
    price       REAL NOT NULL DEFAULT 0,
    currency    TEXT NOT NULL DEFAULT 'USD',
    status      TEXT NOT NULL DEFAULT 'found',
    agent       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    role_agent_key TEXT,
    priority    TEXT NOT NULL DEFAULT 'normal',
    result      TEXT,
    assigned_at TEXT,
    completed_at TEXT,
    client_id   INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    project_id  INTEGER REFERENCES projects(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS agents (
    name        TEXT PRIMARY KEY,
    role        TEXT NOT NULL,
    specialty   TEXT NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('income', 'expense')),
    amount      REAL NOT NULL CHECK (amount > 0),
    currency    TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    task_title TEXT NOT NULL,
    client_name TEXT NOT NULL DEFAULT '',
    amount REAL NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'issued', 'partially_paid', 'paid', 'overdue', 'void')),
    issue_date TEXT,
    due_date TEXT,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE RESTRICT,
    amount REAL NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL,
    payment_date TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'other',
    reference TEXT,
    note TEXT NOT NULL DEFAULT '',
    ledger_id INTEGER REFERENCES ledger(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    amount REAL NOT NULL CHECK (amount > 0),
    refund_date TEXT NOT NULL,
    reference TEXT,
    note TEXT NOT NULL DEFAULT '',
    ledger_id INTEGER REFERENCES ledger(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_refunds_reference
    ON refunds(reference) WHERE reference IS NOT NULL AND reference != '';
CREATE INDEX IF NOT EXISTS idx_refunds_payment ON refunds(payment_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_reference
    ON payments(reference) WHERE reference IS NOT NULL AND reference != '';
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(status);
CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments(invoice_id);

CREATE TABLE IF NOT EXISTS clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL DEFAULT '',
    phone       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    client_id   INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    status      TEXT NOT NULL DEFAULT 'new',
    budget      REAL NOT NULL DEFAULT 0,
    currency    TEXT NOT NULL DEFAULT 'USD',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    agent       TEXT NOT NULL,
    action      TEXT NOT NULL,
    task_id     INTEGER,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    entity_type TEXT,
    entity_id   INTEGER,
    user_name   TEXT NOT NULL DEFAULT 'system',
    details     TEXT NOT NULL DEFAULT '',
    old_values  TEXT,
    new_values  TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_ledger_task ON ledger(task_id);

CREATE TABLE IF NOT EXISTS role_agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    role_agent_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'awaiting_approval'
        CHECK (status IN ('awaiting_approval', 'approved', 'completed', 'rejected')),
    plan_json TEXT NOT NULL,
    result TEXT,
    requested_by TEXT NOT NULL DEFAULT 'system',
    reviewed_by TEXT,
    created_at TEXT NOT NULL,
    reviewed_at TEXT,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_role_agent_runs_task ON role_agent_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_role_agent_runs_status ON role_agent_runs(status);
"""

DEFAULT_AGENTS = (
    ("manager", "manager", "coordinates all agents and assigns tasks"),
    ("finder", "finder", "searches for small paid tasks"),
    ("classifier", "classifier", "analyzes and classifies found tasks"),
    ("executor", "executor", "executes approved tasks by specialty"),
    ("accountant", "accountant", "records income and expenses, produces summaries"),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _audit(conn, action: str, entity_type: str, entity_id: int | None, user_name: str,
           details: str = "", old=None, new=None) -> None:
    """Write one audit row on `conn`, so it commits atomically with the change itself."""
    conn.execute(
        """INSERT INTO activity_logs
           (action, entity_type, entity_id, user_name, details, old_values, new_values, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (action, entity_type, entity_id, user_name, details,
         json.dumps(old, ensure_ascii=False, default=str) if old is not None else None,
         json.dumps(new, ensure_ascii=False, default=str) if new is not None else None,
         _now()),
    )


class Database:
    def __init__(self, path: str):
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


    def vacuum(self) -> None:
        """Rebuild the SQLite database and reclaim unused pages.

        VACUUM must run outside a transaction, so it uses a dedicated
        autocommit connection rather than the regular connect() context.
        """
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        try:
            conn.execute("VACUUM")
        finally:
            conn.close()
        log.info("database vacuum completed for %s", self.path)

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            # Additive migration: preserve the legacy pipeline agent column.
            task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
            for column, declaration in (
                ("role_agent_key", "TEXT"),
                ("priority", "TEXT NOT NULL DEFAULT 'normal'"),
                ("result", "TEXT"),
                ("assigned_at", "TEXT"),
                ("completed_at", "TEXT"),
                ("client_id", "INTEGER REFERENCES clients(id) ON DELETE SET NULL"),
                ("project_id", "INTEGER REFERENCES projects(id) ON DELETE SET NULL"),
            ):
                if column not in task_columns:
                    conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} {declaration}")
            log_columns = {row["name"] for row in conn.execute("PRAGMA table_info(activity_logs)")}
            for column, declaration in (
                ("details", "TEXT NOT NULL DEFAULT ''"),
                ("entity_type", "TEXT"),
                ("entity_id", "INTEGER"),
                ("user_name", "TEXT NOT NULL DEFAULT 'system'"),
                ("old_values", "TEXT"),
                ("new_values", "TEXT"),
            ):
                if column not in log_columns:
                    conn.execute(f"ALTER TABLE activity_logs ADD COLUMN {column} {declaration}")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_role_agent ON tasks(role_agent_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_client ON tasks(client_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id)")
            conn.executemany(
                "INSERT OR IGNORE INTO agents (name, role, specialty) VALUES (?, ?, ?)",
                DEFAULT_AGENTS,
            )
        log.info("database ready at %s", self.path)

    # ---- tasks ----
    def add_task(self, task: dict, user_name: str = "system") -> dict:
        now = _now()
        with self.connect() as conn:
            if task.get("client_id") is not None and conn.execute(
                "SELECT 1 FROM clients WHERE id = ?", (task["client_id"],)
            ).fetchone() is None:
                raise LookupError(f"client #{task['client_id']} not found")
            if task.get("project_id") is not None and conn.execute(
                "SELECT 1 FROM projects WHERE id = ?", (task["project_id"],)
            ).fetchone() is None:
                raise LookupError(f"project #{task['project_id']} not found")
            cur = conn.execute(
                """INSERT INTO tasks
                   (title, description, source, category, price, currency, status, priority,
                    client_id, project_id, created_at, updated_at)
                   VALUES (:title, :description, :source, :category, :price, :currency,
                           'found', :priority, :client_id, :project_id, :now, :now)""",
                {**task, "now": now, "priority": task.get("priority", "normal"),
                 "client_id": task.get("client_id"), "project_id": task.get("project_id")},
            )
            task_id = cur.lastrowid
            created_values = dict(conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone())
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, new_values, created_at)
                   VALUES ('CREATE', 'TASK', ?, ?, ?, ?, ?)""",
                (task_id, user_name, task["title"],
                 json.dumps(created_values, ensure_ascii=False, default=str), now),
            )
        log.info("task #%s added: %s", task_id, task["title"])
        return self.get_task(task_id)

    def list_role_agents(self) -> list[dict]:
        """List the seven business-role agents without mixing pipeline agents."""
        with self.connect() as conn:
            try:
                rows = conn.execute(
                    "SELECT agent_key, name, role FROM role_agents ORDER BY rowid"
                ).fetchall()
            except sqlite3.OperationalError:
                return []
        return [dict(row) for row in rows]

    def assign_role_agent(self, task_id: int, agent_key: str, user_name: str = "system") -> dict:
        """Assign a task to one of the seven role agents and record the event."""
        task = self.get_task(task_id)
        with self.connect() as conn:
            agent = conn.execute(
                "SELECT agent_key FROM role_agents WHERE agent_key = ?", (agent_key,)
            ).fetchone()
            if agent is None:
                raise LookupError(f"role agent {agent_key!r} not found")
            now = _now()
            conn.execute(
                """UPDATE tasks SET role_agent_key = ?, status = 'assigned',
                   assigned_at = ?, completed_at = NULL, updated_at = ? WHERE id = ?""",
                (agent_key, now, now, task_id),
            )
            conn.execute(
                "INSERT INTO activity (agent, action, task_id, created_at) VALUES (?, ?, ?, ?)",
                (agent_key, f"تم إسناد المهمة: {task['title']}", task_id, now),
            )
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, created_at)
                   VALUES ('ASSIGN', 'TASK', ?, ?, ?, ?)""",
                (task_id, user_name, f"{task['title']} → {agent_key}", now),
            )
        log.info("task #%s assigned to role agent %s", task_id, agent_key)
        return self.get_task(task_id)

    def unassign_role_agent(self, task_id: int, user_name: str = "system") -> dict:
        task = self.get_task(task_id)
        now = _now()
        with self.connect() as conn:
            conn.execute(
                "UPDATE tasks SET role_agent_key = NULL, updated_at = ? WHERE id = ?",
                (now, task_id),
            )
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, created_at)
                   VALUES ('UNASSIGN', 'TASK', ?, ?, ?, ?)""",
                (task_id, user_name, task["title"], now),
            )
        return self.get_task(task_id)

    def set_task_status(self, task_id: int, status: str) -> dict:
        """Change task lifecycle state and maintain timestamps/activity history."""
        if status not in TASK_STATUSES:
            raise ValidationError(f"status must be one of: {', '.join(TASK_STATUSES)}")
        task = self.get_task(task_id)
        now = _now()
        completed_at = now if status == "done" else None
        with self.connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = ?, completed_at = ?, updated_at = ? WHERE id = ?",
                (status, completed_at, now, task_id),
            )
            conn.execute(
                "INSERT INTO activity (agent, action, task_id, created_at) VALUES (?, ?, ?, ?)",
                (task.get("role_agent_key") or task.get("agent") or "system",
                 f"تغيير حالة المهمة إلى {status}", task_id, now),
            )
        return self.get_task(task_id)

    def save_task_result(self, task_id: int, result: str) -> dict:
        """Persist an agent's execution result and mark the task complete."""
        if not isinstance(result, str) or not result.strip():
            raise ValidationError("result is required")
        if len(result.strip()) > 20000:
            raise ValidationError("result is too long (max 20000 characters)")
        task = self.get_task(task_id)
        now = _now()
        with self.connect() as conn:
            conn.execute(
                """UPDATE tasks SET result = ?, status = 'done',
                   completed_at = ?, updated_at = ? WHERE id = ?""",
                (result.strip(), now, now, task_id),
            )
            conn.execute(
                "INSERT INTO activity (agent, action, task_id, created_at) VALUES (?, ?, ?, ?)",
                (task.get("role_agent_key") or task.get("agent") or "system",
                 "تم حفظ نتيجة تنفيذ المهمة", task_id, now),
            )
        return self.get_task(task_id)

    # ---- role-agent run approvals ----
    def create_role_agent_run(self, task_id: int, agent_key: str, plan: dict,
                              requested_by: str = "system") -> dict:
        """Persist a role-agent plan; it cannot be treated as approved execution."""
        if not isinstance(plan, dict):
            raise ValidationError("خطة الوكيل غير صالحة.")
        task = self.get_task(task_id)
        if task.get("role_agent_key") != agent_key:
            raise ValidationError("المهمة يجب أن تكون مسندة إلى الوكيل المختار أولاً.")
        with self.connect() as conn:
            if conn.execute(
                "SELECT 1 FROM role_agents WHERE agent_key = ?", (agent_key,)
            ).fetchone() is None:
                raise LookupError(f"role agent {agent_key!r} not found")
            now = _now()
            cur = conn.execute(
                """INSERT INTO role_agent_runs
                   (task_id, role_agent_key, status, plan_json, requested_by, created_at)
                   VALUES (?, ?, 'awaiting_approval', ?, ?, ?)""",
                (task_id, agent_key, json.dumps(plan, ensure_ascii=False), requested_by, now),
            )
            run_id = cur.lastrowid
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, new_values, created_at)
                   VALUES ('AGENT_PLAN_CREATED', 'ROLE_AGENT_RUN', ?, ?, ?, ?, ?)""",
                (run_id, requested_by, f"خطة أولية للمهمة #{task_id} بواسطة {agent_key}",
                 json.dumps({"task_id": task_id, "role_agent_key": agent_key,
                             "status": "awaiting_approval"}, ensure_ascii=False), now),
            )
            conn.execute(
                "INSERT INTO activity (agent, action, task_id, created_at) VALUES (?, ?, ?, ?)",
                (agent_key, f"تم إنشاء خطة تنتظر الموافقة (تشغيل #{run_id})", task_id, now),
            )
        return self.get_role_agent_run(run_id)

    def get_role_agent_run(self, run_id: int) -> dict:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM role_agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise LookupError(f"role-agent run #{run_id} not found")
        item = dict(row)
        item["plan"] = json.loads(item.pop("plan_json"))
        return item

    def list_role_agent_runs(self, task_id: int | None = None, limit: int = 100) -> list[dict]:
        query = "SELECT id FROM role_agent_runs"
        params = ()
        if task_id is not None:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY id DESC LIMIT ?"
        params += (max(1, min(int(limit), 500)),)
        with self.connect() as conn:
            ids = [row["id"] for row in conn.execute(query, params)]
        return [self.get_role_agent_run(run_id) for run_id in ids]

    def review_role_agent_run(self, run_id: int, decision: str, reviewer: str) -> dict:
        if decision not in {"approved", "rejected"}:
            raise ValidationError("قرار المراجعة غير صالح.")
        now = _now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM role_agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"role-agent run #{run_id} not found")
            if row["status"] != "awaiting_approval":
                raise ValidationError("لا يمكن مراجعة هذا التشغيل مرة أخرى.")
            conn.execute(
                """UPDATE role_agent_runs SET status = ?, reviewed_by = ?, reviewed_at = ?
                   WHERE id = ?""",
                (decision, reviewer, now, run_id),
            )
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, old_values, new_values, created_at)
                   VALUES ('AGENT_PLAN_REVIEWED', 'ROLE_AGENT_RUN', ?, ?, ?, ?, ?, ?)""",
                (run_id, reviewer, f"قرار مراجعة خطة المهمة #{row['task_id']}: {decision}",
                 json.dumps({"status": "awaiting_approval"}),
                 json.dumps({"status": decision}), now),
            )
            conn.execute(
                "INSERT INTO activity (agent, action, task_id, created_at) VALUES (?, ?, ?, ?)",
                (row["role_agent_key"], f"مراجعة الخطة: {decision} (تشغيل #{run_id})",
                 row["task_id"], now),
            )
        return self.get_role_agent_run(run_id)

    def complete_role_agent_run(self, run_id: int, result: str, actor: str) -> dict:
        """Record a human-entered outcome after approval; performs no external action."""
        if not isinstance(result, str) or not result.strip():
            raise ValidationError("نتيجة العمل مطلوبة.")
        if len(result.strip()) > 20000:
            raise ValidationError("النتيجة طويلة جداً (الحد 20000 حرف).")
        now = _now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM role_agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise LookupError(f"role-agent run #{run_id} not found")
            if row["status"] != "approved":
                raise ValidationError("يجب اعتماد الخطة قبل تسجيل النتيجة.")
            conn.execute(
                """UPDATE role_agent_runs SET status = 'completed', result = ?, completed_at = ?
                   WHERE id = ?""",
                (result.strip(), now, run_id),
            )
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, old_values, new_values, created_at)
                   VALUES ('AGENT_RUN_COMPLETED', 'ROLE_AGENT_RUN', ?, ?, ?, ?, ?, ?)""",
                (run_id, actor, f"تسجيل نتيجة المهمة #{row['task_id']}",
                 json.dumps({"status": "approved"}),
                 json.dumps({"status": "completed", "result": result.strip()},
                            ensure_ascii=False), now),
            )
            conn.execute(
                "INSERT INTO activity (agent, action, task_id, created_at) VALUES (?, ?, ?, ?)",
                (row["role_agent_key"], f"تم تسجيل نتيجة التشغيل #{run_id}", row["task_id"], now),
            )
        return self.get_role_agent_run(run_id)

    def get_task(self, task_id: int) -> dict:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise LookupError(f"task #{task_id} not found")
        return dict(row)

    def list_tasks(self, status: str | None = None) -> list[dict]:
        query, params = "SELECT * FROM tasks", ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY id DESC"
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(query, params)]

    def update_task(self, task_id: int, *, title: str | None = None, description: str | None = None,
                    status: str | None = None, category: str | None = None,
                    agent: str | None = None, priority: str | None = None,
                    source: str | None = None, price: float | None = None,
                    currency: str | None = None, client_id=_UNSET,
                    project_id=_UNSET, user_name: str = "system") -> dict:
        values = {"title": title, "description": description, "priority": priority,
                  "source": source, "price": price, "currency": currency,
                  "status": status, "category": category, "agent": agent,
                  "client_id": client_id, "project_id": project_id}
        sets, params = ["updated_at = ?"], [_now()]
        for field, value in values.items():
            if value is _UNSET or (value is None and field not in {"client_id", "project_id"}):
                continue
            if field == "priority" and value not in {"low", "normal", "high", "urgent"}:
                raise ValidationError("priority must be low, normal, high or urgent")
            if field == "status" and value not in TASK_STATUSES:
                raise ValidationError("invalid task status")
            if field == "price":
                if isinstance(value, bool) or float(value) < 0:
                    raise ValidationError("price must be zero or more")
                value = float(value)
            sets.append(field + " = ?")
            params.append(value)
        params.append(task_id)
        with self.connect() as conn:
            old_row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if old_row is None:
                raise LookupError("task #{} not found".format(task_id))
            old_values = dict(old_row)
            if client_id is not _UNSET and client_id is not None and conn.execute(
                "SELECT 1 FROM clients WHERE id = ?", (client_id,)
            ).fetchone() is None:
                raise LookupError(f"client #{client_id} not found")
            if project_id is not _UNSET and project_id is not None and conn.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone() is None:
                raise LookupError(f"project #{project_id} not found")
            conn.execute("UPDATE tasks SET " + ", ".join(sets) + " WHERE id = ?", params)
            new_values = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, old_values, new_values, created_at)
                   VALUES ('UPDATE', 'TASK', ?, ?, ?, ?, ?, ?)""",
                (task_id, user_name, new_values["title"],
                 json.dumps(old_values, ensure_ascii=False, default=str),
                 json.dumps(new_values, ensure_ascii=False, default=str), _now()),
            )
        log.info("task #%s updated", task_id)
        return new_values

    def delete_task(self, task_id: int, user_name: str = "system") -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                raise LookupError("task #{} not found".format(task_id))
            task = dict(row)
            # Detach linked financial records explicitly so every relationship change
            # is audited in the same transaction as task deletion.
            for table, entity_type in (("ledger", "LEDGER"), ("invoices", "INVOICE")):
                linked_rows = conn.execute(
                    f"SELECT * FROM {table} WHERE task_id = ? ORDER BY id", (task_id,)
                ).fetchall()
                for linked_row in linked_rows:
                    before = dict(linked_row)
                    conn.execute(
                        f"UPDATE {table} SET task_id = NULL WHERE id = ?",
                        (before["id"],),
                    )
                    after = dict(conn.execute(
                        f"SELECT * FROM {table} WHERE id = ?", (before["id"],)
                    ).fetchone())
                    _audit(
                        conn, "UNLINK_TASK", entity_type, before["id"], user_name,
                        f"Detached from deleted task #{task_id}", old=before, new=after,
                    )
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, old_values, new_values, created_at)
                   VALUES ('DELETE', 'TASK', ?, ?, ?, ?, NULL, ?)""",
                (task_id, user_name, task["title"],
                 json.dumps(task, ensure_ascii=False, default=str), _now()),
            )
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        log.info("task #%s deleted", task_id)

    def get_tasks(self) -> list[dict]:
        """Return tasks with the legacy pipeline agent display name."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT t.*, a.name AS agent_name
                   FROM tasks t LEFT JOIN agents a ON t.agent = a.name
                   ORDER BY t.id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def add_system_log(self, action: str, details: str = "", *,
                       entity_type: str | None = None, entity_id: int | None = None,
                       user_name: str = "system", old_values=None, new_values=None) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO activity_logs
                   (action, entity_type, entity_id, user_name, details, old_values, new_values, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (action, entity_type, entity_id, user_name, details,
                 json.dumps(old_values, ensure_ascii=False, default=str) if old_values is not None else None,
                 json.dumps(new_values, ensure_ascii=False, default=str) if new_values is not None else None,
                 _now()),
            )

    def list_system_logs(self, limit: int = 200) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT id, action, entity_type, entity_id, user_name, details, old_values, new_values, created_at
                   FROM activity_logs ORDER BY id DESC LIMIT ?""",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()
        return [dict(row) for row in rows]

    # ---- clients ----
    def add_client(self, client: dict, user_name: str = "system") -> dict:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO clients (name, email, phone, created_at) VALUES (:name, :email, :phone, :now)",
                {**client, "now": _now()},
            )
            row = dict(conn.execute("SELECT * FROM clients WHERE id = ?", (cur.lastrowid,)).fetchone())
            _audit(conn, "CREATE", "CLIENT", row["id"], user_name, row["name"], new=row)
        log.info("client #%s added: %s", row["id"], client["name"])
        return row

    def list_clients(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY id DESC")]

    def update_client(self, client_id: int, client: dict, user_name: str = "system") -> dict:
        with self.connect() as conn:
            old = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
            if old is None:
                raise LookupError(f"client #{client_id} not found")
            conn.execute(
                "UPDATE clients SET name = :name, email = :email, phone = :phone WHERE id = :id",
                {**client, "id": client_id},
            )
            row = dict(conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone())
            _audit(conn, "UPDATE", "CLIENT", client_id, user_name, row["name"],
                   old=dict(old), new=row)
        log.info("client #%s updated", client_id)
        return row

    def delete_client(self, client_id: int, user_name: str = "system") -> None:
        with self.connect() as conn:
            old = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
            if old is None:
                raise LookupError(f"client #{client_id} not found")
            _audit(conn, "DELETE", "CLIENT", client_id, user_name, old["name"], old=dict(old))
            conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        log.info("client #%s deleted", client_id)

    # ---- projects ----
    def add_project(self, project: dict, user_name: str = "system") -> dict:
        if project.get("client_id") is not None:
            with self.connect() as conn:
                if conn.execute("SELECT 1 FROM clients WHERE id = ?", (project["client_id"],)).fetchone() is None:
                    raise LookupError(f"client #{project['client_id']} not found")
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO projects (name, client_id, status, budget, currency, created_at)
                   VALUES (:name, :client_id, :status, :budget, :currency, :now)""",
                {**project, "now": _now()},
            )
            project_id = cur.lastrowid
            created = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
            _audit(conn, "CREATE", "PROJECT", project_id, user_name, created["name"], new=created)
        log.info("project #%s added: %s", project_id, project["name"])
        return self.list_projects(project_id)[0]

    def list_projects(self, project_id: int | None = None) -> list[dict]:
        query = """SELECT p.*, c.name AS client_name
                   FROM projects p LEFT JOIN clients c ON c.id = p.client_id"""
        params: tuple = ()
        if project_id is not None:
            query += " WHERE p.id = ?"
            params = (project_id,)
        query += " ORDER BY p.id DESC"
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(query, params)]

    def update_project(self, project_id: int, project: dict, user_name: str = "system") -> dict:
        if project.get("client_id") is not None:
            with self.connect() as conn:
                if conn.execute("SELECT 1 FROM clients WHERE id = ?", (project["client_id"],)).fetchone() is None:
                    raise LookupError(f"client #{project['client_id']} not found")
        with self.connect() as conn:
            old = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if old is None:
                raise LookupError(f"project #{project_id} not found")
            conn.execute(
                """UPDATE projects SET name = :name, client_id = :client_id, status = :status,
                          budget = :budget, currency = :currency WHERE id = :id""",
                {**project, "id": project_id},
            )
            new = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
            _audit(conn, "UPDATE", "PROJECT", project_id, user_name, new["name"],
                   old=dict(old), new=new)
        log.info("project #%s updated", project_id)
        return self.list_projects(project_id)[0]

    def set_project_status(self, project_id: int, status: str, user_name: str = "system") -> None:
        with self.connect() as conn:
            old = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if old is None:
                raise LookupError(f"project #{project_id} not found")
            conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
            _audit(conn, "UPDATE", "PROJECT", project_id, user_name, old["name"],
                   old={"status": old["status"]}, new={"status": status})

    def delete_project(self, project_id: int, user_name: str = "system") -> None:
        with self.connect() as conn:
            old = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if old is None:
                raise LookupError(f"project #{project_id} not found")
            _audit(conn, "DELETE", "PROJECT", project_id, user_name, old["name"], old=dict(old))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        log.info("project #%s deleted", project_id)

    def seed_demo(self) -> bool:
        """Insert demo rows once. Returns False if the database already has clients."""
        if self.list_clients():
            return False
        ids = [
            self.add_client({"name": n, "email": e, "phone": ""})["id"]
            for n, e in (("شركة الأطلس", "atlas@example.com"),
                         ("شركة النخبة", "elite@example.com"),
                         ("شركة المستقبل", "future@example.com"))
        ]
        for name, cid, status, budget in (
            ("موقع الشركة", ids[0], "in_progress", 800),
            ("منصة العملاء", ids[1], "done", 1500),
            ("تطبيق الهاتف", ids[2], "new", 2500),
        ):
            self.add_project({"name": name, "client_id": cid, "status": status,
                              "budget": budget, "currency": "USD"})
        for title, agent, status, price in (
            ("تصميم الواجهة", "executor", "in_progress", 60),
            ("إطلاق حملة إعلانية", "manager", "found", 40),
            ("تحليل السوق", "classifier", "done", 25),
        ):
            task = self.add_task({"title": title, "description": "", "source": "demo",
                                  "category": "", "price": price, "currency": "USD"})
            self.update_task(task["id"], status=status, agent=agent)
        return True

    # ---- activity log ----
    def add_activity(self, agent: str, action: str, task_id: int | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO activity (agent, action, task_id, created_at) VALUES (?, ?, ?, ?)",
                (agent, action, task_id, _now()),
            )

    def list_activity(self, limit: int = 50) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,))]

    def tasks_missing_income(self) -> list[dict]:
        """Completed tasks with a price that have no income entry in the ledger yet."""
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT t.* FROM tasks t
                   WHERE t.status = 'done' AND t.price > 0
                     AND NOT EXISTS (SELECT 1 FROM ledger l WHERE l.task_id = t.id AND l.kind = 'income')
                   ORDER BY t.id""")]

    # ---- agents ----
    def list_agents(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM agents ORDER BY name")]

    # ---- invoices and payments ----
    def create_invoice(self, task_id: int, due_date: str | None = None,
                       notes: str = "", user_name: str = "system") -> dict:
        """Create a draft invoice with immutable task/client name and amount snapshots."""
        with self.connect() as conn:
            task = conn.execute(
                """SELECT t.id, t.title, t.price, t.currency, t.client_id,
                          COALESCE(c.name, '') AS client_name
                   FROM tasks t LEFT JOIN clients c ON c.id = t.client_id
                   WHERE t.id = ?""", (task_id,)
            ).fetchone()
            if task is None:
                raise LookupError(f"task #{task_id} not found")
            if float(task["price"]) <= 0:
                raise ValueError("task price must be greater than zero to create an invoice")
            now = _now()
            cur = conn.execute(
                """INSERT INTO invoices
                   (invoice_number, task_id, client_id, task_title, client_name, amount,
                    currency, status, due_date, notes, created_at, updated_at)
                   VALUES ('PENDING', ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)""",
                (task_id, task["client_id"], task["title"], task["client_name"],
                 task["price"], task["currency"], due_date, notes, now, now),
            )
            invoice_id = cur.lastrowid
            invoice_number = f"INV-{datetime.now(timezone.utc):%Y%m%d}-{invoice_id:06d}"
            conn.execute("UPDATE invoices SET invoice_number = ? WHERE id = ?",
                         (invoice_number, invoice_id))
            row = dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone())
            _audit(conn, "CREATE", "INVOICE", invoice_id, user_name,
                   f"Created draft {invoice_number}", new=row)
        return row

    def issue_invoice(self, invoice_id: int, user_name: str = "system") -> dict:
        with self.connect() as conn:
            old_row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if old_row is None:
                raise LookupError(f"invoice #{invoice_id} not found")
            old = dict(old_row)
            if old["status"] != "draft":
                raise ValueError("only draft invoices can be issued")
            now = _now()
            conn.execute(
                "UPDATE invoices SET status = 'issued', issue_date = ?, updated_at = ? WHERE id = ?",
                (now[:10], now, invoice_id),
            )
            new = dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone())
            _audit(conn, "ISSUE", "INVOICE", invoice_id, user_name,
                   f"Issued {new['invoice_number']}", old=old, new=new)
        return new

    def mark_overdue_invoices(self, today: str | None = None,
                              user_name: str = "system") -> list[dict]:
        """Transition due issued/part-paid invoices to overdue, auditing each change."""
        from datetime import date

        business_date = today or datetime.now(timezone.utc).date().isoformat()
        try:
            date.fromisoformat(business_date)
        except (TypeError, ValueError):
            raise ValueError("today must use YYYY-MM-DD format") from None

        transitioned = []
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM invoices
                   WHERE status IN ('issued', 'partially_paid')
                     AND due_date IS NOT NULL AND due_date < ?
                   ORDER BY id""",
                (business_date,),
            ).fetchall()
            for row in rows:
                old = dict(row)
                now = _now()
                conn.execute(
                    "UPDATE invoices SET status = 'overdue', updated_at = ? WHERE id = ?",
                    (now, old["id"]),
                )
                new = dict(conn.execute(
                    "SELECT * FROM invoices WHERE id = ?", (old["id"],)
                ).fetchone())
                _audit(conn, "OVERDUE", "INVOICE", old["id"], user_name,
                       f"Invoice {old['invoice_number']} passed due date {old['due_date']}",
                       old=old, new=new)
                transitioned.append(new)
        return transitioned

    def record_payment(self, invoice_id: int, amount: float, currency: str,
                       payment_date: str, method: str = "other", reference: str | None = None,
                       note: str = "", user_name: str = "system") -> dict:
        """Record a payment and its income ledger row atomically; references are idempotent."""
        with self.connect() as conn:
            invoice_row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if invoice_row is None:
                raise LookupError(f"invoice #{invoice_id} not found")
            invoice = dict(invoice_row)
            if invoice["status"] not in {"issued", "partially_paid", "overdue"}:
                raise ValueError("payments can only be recorded against issued invoices")
            if currency != invoice["currency"]:
                raise ValueError("payment currency must match invoice currency")
            if amount <= 0:
                raise ValueError("payment amount must be greater than zero")
            if reference:
                existing = conn.execute("SELECT id FROM payments WHERE reference = ?",
                                         (reference,)).fetchone()
                if existing:
                    raise ValueError(f"payment reference already exists: {reference}")
            paid = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()["total"]
            remaining = round(float(invoice["amount"]) - float(paid), 2)
            if amount > remaining + 0.000001:
                raise ValueError(f"payment exceeds remaining balance ({remaining:.2f})")
            now = _now()
            ledger_cur = conn.execute(
                """INSERT INTO ledger (task_id, kind, amount, currency, note, created_at)
                   VALUES (?, 'income', ?, ?, ?, ?)""",
                (invoice["task_id"], amount, currency,
                 f"Payment for {invoice['invoice_number']}" + (f" — {note}" if note else ""), now),
            )
            payment_cur = conn.execute(
                """INSERT INTO payments
                   (invoice_id, amount, currency, payment_date, method, reference, note, ledger_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (invoice_id, amount, currency, payment_date, method, reference or None,
                 note, ledger_cur.lastrowid, now),
            )
            payment = dict(conn.execute("SELECT * FROM payments WHERE id = ?",
                                        (payment_cur.lastrowid,)).fetchone())
            new_status = "paid" if amount >= remaining - 0.000001 else "partially_paid"
            conn.execute("UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?",
                         (new_status, now, invoice_id))
            updated_invoice = dict(conn.execute("SELECT * FROM invoices WHERE id = ?",
                                                 (invoice_id,)).fetchone())
            _audit(conn, "CREATE", "PAYMENT", payment["id"], user_name,
                   f"Payment {amount:g} {currency} for {invoice['invoice_number']}",
                   new=payment)
            _audit(conn, "PAYMENT_STATUS", "INVOICE", invoice_id, user_name,
                   f"{invoice['status']} -> {new_status}", old=invoice, new=updated_invoice)
        return payment

    def void_invoice(self, invoice_id: int, reason: str, user_name: str = "system") -> dict:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if row is None:
                raise LookupError(f"invoice #{invoice_id} not found")
            old = dict(row)
            paid = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()["total"]
            if float(paid) > 0:
                raise ValueError("invoice with recorded payments cannot be voided; refund payments first")
            if old["status"] not in {"draft", "issued", "overdue"}:
                raise ValueError("only unpaid draft or issued invoices can be voided")
            now = _now()
            conn.execute(
                "UPDATE invoices SET status = 'void', notes = ?, updated_at = ? WHERE id = ?",
                ((old["notes"] + "\nVoid: " + reason).strip(), now, invoice_id),
            )
            new = dict(conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone())
            _audit(conn, "VOID", "INVOICE", invoice_id, user_name,
                   f"Voided {old['invoice_number']}: {reason}", old=old, new=new)
        return new

    def refund_payment(self, payment_id: int, amount: float, refund_date: str,
                       reference: str | None = None, note: str = "",
                       user_name: str = "system") -> dict:
        """Record a partial/full refund and matching expense ledger entry atomically."""
        with self.connect() as conn:
            payment_row = conn.execute(
                """SELECT p.*, i.task_id, i.invoice_number, i.id AS invoice_id,
                          i.amount AS invoice_amount
                   FROM payments p JOIN invoices i ON i.id = p.invoice_id
                   WHERE p.id = ?""", (payment_id,)
            ).fetchone()
            if payment_row is None:
                raise LookupError(f"payment #{payment_id} not found")
            payment = dict(payment_row)
            if amount <= 0:
                raise ValueError("refund amount must be greater than zero")
            refunded = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS total FROM refunds WHERE payment_id = ?",
                (payment_id,),
            ).fetchone()["total"]
            remaining_refundable = round(float(payment["amount"]) - float(refunded), 2)
            if amount > remaining_refundable + 0.000001:
                raise ValueError(
                    f"refund exceeds refundable payment balance ({remaining_refundable:.2f})"
                )
            if reference and conn.execute(
                "SELECT 1 FROM refunds WHERE reference = ?", (reference,)
            ).fetchone():
                raise ValueError(f"refund reference already exists: {reference}")
            now = _now()
            ledger_cur = conn.execute(
                """INSERT INTO ledger (task_id, kind, amount, currency, note, created_at)
                   VALUES (?, 'expense', ?, ?, ?, ?)""",
                (payment["task_id"], amount, payment["currency"],
                 f"Refund for {payment['invoice_number']}" + (f" — {note}" if note else ""), now),
            )
            refund_cur = conn.execute(
                """INSERT INTO refunds
                   (payment_id, amount, refund_date, reference, note, ledger_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (payment_id, amount, refund_date, reference or None, note,
                 ledger_cur.lastrowid, now),
            )
            refund = dict(conn.execute(
                "SELECT * FROM refunds WHERE id = ?", (refund_cur.lastrowid,)
            ).fetchone())
            invoice_id = payment["invoice_id"]
            old_invoice = dict(conn.execute(
                "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
            ).fetchone())
            total_paid = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ?",
                (invoice_id,),
            ).fetchone()[0]
            total_refunded = conn.execute(
                """SELECT COALESCE(SUM(r.amount), 0)
                   FROM refunds r JOIN payments p ON p.id = r.payment_id
                   WHERE p.invoice_id = ?""", (invoice_id,)
            ).fetchone()[0]
            net_paid = round(float(total_paid) - float(total_refunded), 2)
            if net_paid <= 0:
                new_status = "issued"
            elif net_paid + 0.000001 >= float(old_invoice["amount"]):
                new_status = "paid"
            else:
                new_status = "partially_paid"
            conn.execute(
                "UPDATE invoices SET status = ?, updated_at = ? WHERE id = ?",
                (new_status, now, invoice_id),
            )
            new_invoice = dict(conn.execute(
                "SELECT * FROM invoices WHERE id = ?", (invoice_id,)
            ).fetchone())
            _audit(conn, "CREATE", "REFUND", refund["id"], user_name,
                   f"Refund {amount:g} {payment['currency']} for {payment['invoice_number']}",
                   new=refund)
            _audit(conn, "REFUND_STATUS", "INVOICE", invoice_id, user_name,
                   f"{old_invoice['status']} -> {new_status}", old=old_invoice, new=new_invoice)
        return refund

    def list_refunds(self, payment_id: int | None = None) -> list[dict]:
        query = """SELECT r.*, p.invoice_id, i.invoice_number
                   FROM refunds r JOIN payments p ON p.id = r.payment_id
                   JOIN invoices i ON i.id = p.invoice_id"""
        params = ()
        if payment_id is not None:
            query += " WHERE r.payment_id = ?"
            params = (payment_id,)
        query += " ORDER BY r.id DESC"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    def list_invoices(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT i.*,
                          COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) AS paid_amount,
                          COALESCE((SELECT SUM(r.amount) FROM refunds r
                                    JOIN payments p ON p.id = r.payment_id
                                    WHERE p.invoice_id = i.id), 0) AS refunded_amount,
                          COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0)
                          - COALESCE((SELECT SUM(r.amount) FROM refunds r
                                      JOIN payments p ON p.id = r.payment_id
                                      WHERE p.invoice_id = i.id), 0) AS net_paid_amount
                   FROM invoices i ORDER BY i.id DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def list_payments(self, invoice_id: int | None = None) -> list[dict]:
        query = """SELECT p.*, i.invoice_number FROM payments p
                   JOIN invoices i ON i.id = p.invoice_id"""
        params = ()
        if invoice_id is not None:
            query += " WHERE p.invoice_id = ?"
            params = (invoice_id,)
        query += " ORDER BY p.id DESC"
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params)]

    # ---- ledger ----
    def add_ledger_entry(self, entry: dict, user_name: str = "system") -> dict:
        if entry.get("task_id") is not None:
            self.get_task(entry["task_id"])
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO ledger (task_id, kind, amount, currency, note, created_at)
                   VALUES (:task_id, :kind, :amount, :currency, :note, :now)""",
                {**entry, "now": _now()},
            )
            row = dict(conn.execute("SELECT * FROM ledger WHERE id = ?", (cur.lastrowid,)).fetchone())
            _audit(conn, "CREATE", "LEDGER", row["id"], user_name,
                   f"{row['kind']} {row['amount']:g} {row['currency']}", new=row)
        log.info("ledger %s %.2f %s", entry["kind"], entry["amount"], entry["currency"])
        return row

    def update_ledger_entry(self, entry_id: int, entry: dict, user_name: str = "system") -> dict:
        """Update a ledger row and atomically record before/after audit snapshots."""
        with self.connect() as conn:
            old_row = conn.execute("SELECT * FROM ledger WHERE id = ?", (entry_id,)).fetchone()
            if old_row is None:
                raise LookupError(f"ledger entry #{entry_id} not found")
            linked = conn.execute(
                "SELECT 1 FROM payments WHERE ledger_id = ? UNION ALL "
                "SELECT 1 FROM refunds WHERE ledger_id = ? LIMIT 1",
                (entry_id, entry_id),
            ).fetchone()
            if linked:
                raise ValueError("ledger entries generated by payments or refunds cannot be edited")
            if entry.get("task_id") is not None and conn.execute(
                "SELECT 1 FROM tasks WHERE id = ?", (entry["task_id"],)
            ).fetchone() is None:
                raise LookupError(f"task #{entry['task_id']} not found")
            old = dict(old_row)
            conn.execute(
                """UPDATE ledger SET task_id = :task_id, kind = :kind, amount = :amount,
                   currency = :currency, note = :note WHERE id = :id""",
                {**entry, "id": entry_id},
            )
            new = dict(conn.execute("SELECT * FROM ledger WHERE id = ?", (entry_id,)).fetchone())
            _audit(conn, "UPDATE", "LEDGER", entry_id, user_name,
                   f"{new['kind']} {new['amount']:g} {new['currency']}",
                   old=old, new=new)
        log.info("ledger entry #%s updated", entry_id)
        return new

    def delete_ledger_entry(self, entry_id: int, user_name: str = "system") -> None:
        """Delete a ledger row while retaining its complete audit snapshot."""
        with self.connect() as conn:
            old_row = conn.execute("SELECT * FROM ledger WHERE id = ?", (entry_id,)).fetchone()
            if old_row is None:
                raise LookupError(f"ledger entry #{entry_id} not found")
            linked = conn.execute(
                "SELECT 1 FROM payments WHERE ledger_id = ? UNION ALL "
                "SELECT 1 FROM refunds WHERE ledger_id = ? LIMIT 1",
                (entry_id, entry_id),
            ).fetchone()
            if linked:
                raise ValueError("ledger entries generated by payments or refunds cannot be deleted")
            old = dict(old_row)
            _audit(conn, "DELETE", "LEDGER", entry_id, user_name,
                   f"{old['kind']} {old['amount']:g} {old['currency']}", old=old)
            conn.execute("DELETE FROM ledger WHERE id = ?", (entry_id,))
        log.info("ledger entry #%s deleted", entry_id)

    def list_ledger(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM ledger ORDER BY id DESC")]

    def summary(self) -> dict:
        """Totals per currency (currencies are never mixed) and task counts per status."""
        with self.connect() as conn:
            money = conn.execute(
                """SELECT currency,
                          ROUND(SUM(CASE WHEN kind = 'income'  THEN amount ELSE 0 END), 2) AS income,
                          ROUND(SUM(CASE WHEN kind = 'expense' THEN amount ELSE 0 END), 2) AS expense
                   FROM ledger GROUP BY currency ORDER BY currency"""
            ).fetchall()
            counts = conn.execute(
                "SELECT status, COUNT(*) AS n FROM tasks GROUP BY status"
            ).fetchall()
        return {
            "money": [
                {**dict(r), "profit": round(r["income"] - r["expense"], 2)} for r in money
            ],
            "tasks": {r["status"]: r["n"] for r in counts},
        }
