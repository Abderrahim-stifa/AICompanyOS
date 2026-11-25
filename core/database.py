"""SQLite storage for tasks, agents and the accounting ledger."""
from __future__ import annotations

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
    updated_at  TEXT NOT NULL
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

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            conn.executemany(
                "INSERT OR IGNORE INTO agents (name, role, specialty) VALUES (?, ?, ?)",
                DEFAULT_AGENTS,
            )
        log.info("database ready at %s", self.path)

    # ---- tasks ----
    def add_task(self, task: dict) -> dict:
        now = _now()
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO tasks
                   (title, description, source, category, price, currency, status, created_at, updated_at)
                   VALUES (:title, :description, :source, :category, :price, :currency, 'found', :now, :now)""",
                {**task, "now": now},
            )
            task_id = cur.lastrowid
        log.info("task #%s added: %s", task_id, task["title"])
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

    def update_task(self, task_id: int, *, status: str | None = None,
                    category: str | None = None, agent: str | None = None) -> dict:
        self.get_task(task_id)  # raises LookupError if missing
        sets, params = ["updated_at = ?"], [_now()]
        if status is not None:
            if status not in TASK_STATUSES:
                raise ValidationError(f"status must be one of: {', '.join(TASK_STATUSES)}")
            sets.append("status = ?")
            params.append(status)
        if category is not None:
            sets.append("category = ?")
            params.append(category)
        if agent is not None:
            sets.append("agent = ?")
            params.append(agent)
        params.append(task_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", params)
        log.info("task #%s updated", task_id)
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> None:
        self.get_task(task_id)
        with self.connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        log.info("task #%s deleted", task_id)

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
