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
    completed_at TEXT
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
            conn.executemany(
                "INSERT OR IGNORE INTO agents (name, role, specialty) VALUES (?, ?, ?)",
                DEFAULT_AGENTS,
            )
        log.info("database ready at %s", self.path)

    # ---- tasks ----
    def add_task(self, task: dict, user_name: str = "system") -> dict:
        now = _now()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO tasks
                   (title, description, source, category, price, currency, status, priority, created_at, updated_at)
                   VALUES (:title, :description, :source, :category, :price, :currency, 'found', :priority, :now, :now)""",
                {**task, "now": now, "priority": task.get("priority", "normal")},
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
                    currency: str | None = None, user_name: str = "system") -> dict:
        values = {"title": title, "description": description, "priority": priority,
                  "source": source, "price": price, "currency": currency,
                  "status": status, "category": category, "agent": agent}
        sets, params = ["updated_at = ?"], [_now()]
        for field, value in values.items():
            if value is None:
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
    def add_client(self, client: dict) -> dict:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO clients (name, email, phone, created_at) VALUES (:name, :email, :phone, :now)",
                {**client, "now": _now()},
            )
            row = conn.execute("SELECT * FROM clients WHERE id = ?", (cur.lastrowid,)).fetchone()
        log.info("client #%s added: %s", row["id"], client["name"])
        return dict(row)

    def list_clients(self) -> list[dict]:
        with self.connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM clients ORDER BY id DESC")]

    def update_client(self, client_id: int, client: dict) -> dict:
        with self.connect() as conn:
            cur = conn.execute(
                "UPDATE clients SET name = :name, email = :email, phone = :phone WHERE id = :id",
                {**client, "id": client_id},
            )
            if cur.rowcount == 0:
                raise LookupError(f"client #{client_id} not found")
            row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        log.info("client #%s updated", client_id)
        return dict(row)

    def delete_client(self, client_id: int) -> None:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            if cur.rowcount == 0:
                raise LookupError(f"client #{client_id} not found")
        log.info("client #%s deleted", client_id)

    # ---- projects ----
    def add_project(self, project: dict) -> dict:
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

    def update_project(self, project_id: int, project: dict) -> dict:
        if project.get("client_id") is not None:
            with self.connect() as conn:
                if conn.execute("SELECT 1 FROM clients WHERE id = ?", (project["client_id"],)).fetchone() is None:
                    raise LookupError(f"client #{project['client_id']} not found")
        with self.connect() as conn:
            cur = conn.execute(
                """UPDATE projects SET name = :name, client_id = :client_id, status = :status,
                          budget = :budget, currency = :currency WHERE id = :id""",
                {**project, "id": project_id},
            )
            if cur.rowcount == 0:
                raise LookupError(f"project #{project_id} not found")
        log.info("project #%s updated", project_id)
        return self.list_projects(project_id)[0]

    def set_project_status(self, project_id: int, status: str) -> None:
        with self.connect() as conn:
            cur = conn.execute("UPDATE projects SET status = ? WHERE id = ?", (status, project_id))
            if cur.rowcount == 0:
                raise LookupError(f"project #{project_id} not found")

    def delete_project(self, project_id: int) -> None:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            if cur.rowcount == 0:
                raise LookupError(f"project #{project_id} not found")
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

    # ---- ledger ----
    def add_ledger_entry(self, entry: dict) -> dict:
        if entry.get("task_id") is not None:
            self.get_task(entry["task_id"])
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO ledger (task_id, kind, amount, currency, note, created_at)
                   VALUES (:task_id, :kind, :amount, :currency, :note, :now)""",
                {**entry, "now": _now()},
            )
            row = conn.execute("SELECT * FROM ledger WHERE id = ?", (cur.lastrowid,)).fetchone()
        log.info("ledger %s %.2f %s", entry["kind"], entry["amount"], entry["currency"])
        return dict(row)

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
