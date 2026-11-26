# AICompanyOS SQLite schema — v0.3.7

## Database lifecycle

The application initializes SQLite through `Company()` → `Database.init()`.
Initialization uses `CREATE TABLE IF NOT EXISTS` and `INSERT OR IGNORE` for the
five built-in pipeline agents. It is safe to call repeatedly and does not drop
existing tables or rows.

The default database path is configured by `core/settings.py` under
`data/aicompanyos.db` (or `AICOS_DATA_DIR`). The database is local to the
installation unless the operator changes that setting.

## Tables

### `agents` — pipeline agents

| Column | Type | Constraints | Meaning |
|---|---|---|---|
| name | TEXT | PRIMARY KEY | Stable pipeline agent key |
| role | TEXT | NOT NULL | Pipeline role |
| specialty | TEXT | NOT NULL DEFAULT '' | Human-readable responsibility |
| enabled | INTEGER | NOT NULL DEFAULT 1 | Whether the pipeline agent is enabled |

Seeded records: manager, finder, classifier, executor, accountant.

### `tasks`

| Column | Type | Constraints | Meaning |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Task identifier |
| title | TEXT | NOT NULL | Task title |
| description | TEXT | NOT NULL DEFAULT '' | Description |
| source | TEXT | NOT NULL DEFAULT '' | Origin |
| category | TEXT | NOT NULL DEFAULT '' | Classification |
| price | REAL | NOT NULL DEFAULT 0 | Expected amount |
| currency | TEXT | NOT NULL DEFAULT 'USD' | Currency code |
| status | TEXT | NOT NULL DEFAULT 'found' | Workflow state |
| agent | TEXT | NOT NULL DEFAULT '' | Assigned pipeline/role agent |
| created_at | TEXT | NOT NULL | UTC creation timestamp |
| updated_at | TEXT | NOT NULL | UTC update timestamp |

### `clients`

`id INTEGER PRIMARY KEY`, `name TEXT NOT NULL`, `email TEXT NOT NULL DEFAULT ''`,
`phone TEXT NOT NULL DEFAULT ''`, `created_at TEXT NOT NULL`.

### `projects`

`id INTEGER PRIMARY KEY`, `name TEXT NOT NULL`,
`client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL`,
`status TEXT NOT NULL DEFAULT 'new'`, `budget REAL NOT NULL DEFAULT 0`,
`currency TEXT NOT NULL DEFAULT 'USD'`, `created_at TEXT NOT NULL`.

### `ledger`

`id INTEGER PRIMARY KEY`, `task_id INTEGER REFERENCES tasks(id) ON DELETE SET NULL`,
`kind TEXT NOT NULL CHECK (kind IN ('income', 'expense'))`,
`amount REAL NOT NULL CHECK (amount > 0)`, `currency TEXT NOT NULL`,
`note TEXT NOT NULL DEFAULT ''`, `created_at TEXT NOT NULL`.

### `activity`

`id INTEGER PRIMARY KEY`, `agent TEXT NOT NULL`, `action TEXT NOT NULL`,
`task_id INTEGER`, `created_at TEXT NOT NULL`.

## Indexes

- `idx_tasks_status` on `tasks(status)`
- `idx_ledger_task` on `ledger(task_id)`

## Agent Center model

The seven role agents (CEO, Research, Consultant, Engineer, Marketing, Accountant,
Market Analyst) are currently defined in `core/ai_agents.py`. They are
rule-based/offline planners, not independently running LLM processes. The
`core/agent_center.py` module derives their task counts from the existing
`tasks.agent` field. The five pipeline agents in the `agents` table are a
separate subsystem and must not be conflated with the seven role agents.

## Migration policy

Schema changes must be additive and idempotent. Never drop/recreate the user's
database to apply a v0.1 update. Back up the database before any future
destructive migration. This document describes the current schema through v0.3.7;
it does not claim that a separate agent execution-history table exists.
