# AICompanyOS SQLite schema — application v0.5.0

This document describes the repository's current SQLite model. The application
version is maintained separately from the database schema: schema changes use
additive, idempotent initialization and migrations rather than destructive
recreation.

## Database lifecycle

The application initializes the core schema through `Company()` →
`initialize_database()` → `Database.init()`. The bootstrap also creates the
seven-role-agent registry and persisted UI settings. The deliverable workspace
store creates its two tables when that feature is initialized.

Initialization uses `CREATE TABLE IF NOT EXISTS`, guarded `ALTER TABLE`
operations, and `INSERT OR IGNORE` for built-in records. It does not drop or
recreate existing user tables. SQLite foreign-key enforcement is enabled on
application database connections.

The default database path is `data/aicompanyos.db`, configurable through
`AICOS_DATA_DIR` / `AICOS_DB_PATH`. The database is local to the installation.

## Core business tables

### `tasks`

| Column | Type | Meaning |
|---|---|---|
| id | INTEGER PRIMARY KEY | Task identifier |
| title, description | TEXT | Task name and details |
| source, category | TEXT | Origin and classification |
| price | REAL | Expected task amount |
| currency | TEXT | Currency code |
| status | TEXT | Workflow status |
| agent | TEXT | Legacy pipeline-agent assignment |
| role_agent_key | TEXT | Optional role-agent assignment |
| priority | TEXT | Task priority |
| result | TEXT | Human-entered completion result |
| assigned_at, completed_at | TEXT | Lifecycle timestamps |
| client_id | INTEGER FK → clients.id | Optional client; set NULL on client deletion |
| project_id | INTEGER FK → projects.id | Optional project; set NULL on project deletion |
| created_at, updated_at | TEXT | Timestamps |

### `clients`

`id` (primary key), `name`, `email`, `phone`, `created_at`.

### `projects`

`id` (primary key), `name`, `client_id` (optional FK to clients with
ON DELETE SET NULL), `status`, `budget`, `currency`, `created_at`.

### `agents` — five pipeline agents

`name` (primary key), `role`, `specialty`, `enabled`. Built-in records:
manager, finder, classifier, executor, accountant.

### `role_agents` — seven business-role agents

`agent_key` (primary key), `name`, `role`, `status`,
`tasks_count`, `last_activity`. The seven keys are CEO, Engineer,
Marketing, Research, Consultant, Accountant, and Market Analyst. This registry
is distinct from the five-row pipeline `agents` table.

## Finance tables

### `ledger`

`id` (primary key), optional `task_id` FK to tasks (ON DELETE SET NULL),
`kind` (income or expense), positive `amount`, `currency`, `note`,
`created_at`.

### `invoices`

Stores invoice number, optional task/client references, task/client name
snapshots, positive amount, currency, status, issue/due dates, notes, and
creation/update timestamps. Status is constrained to draft, issued,
partially_paid, paid, overdue, or void. Invoice number is unique.

### `payments`

Stores invoice FK (ON DELETE RESTRICT), positive amount, currency, payment
date, method, optional unique reference, note, optional linked ledger row,
and creation timestamp. A recorded payment and its income-ledger entry are
created transactionally.

### `refunds`

Stores payment FK (ON DELETE RESTRICT), positive amount, refund date, optional
unique reference, note, optional linked ledger row, and creation timestamp.
Refunds create reversal expense entries; payment/refund source ledger entries
are protected from ordinary manual edits/deletes.

## Agent workflow and audit tables

### `role_agent_runs`

Stores task FK (ON DELETE CASCADE), role-agent key, status, JSON plan, optional
result, requester/reviewer, and created/reviewed/completed timestamps. Status
values are awaiting_approval, approved, completed, or rejected. A plan record
is not proof that an agent executed external work. Completion results are
entered and reviewed by a human.

### `activity`

Legacy operational activity stream: `id`, `agent`, `action`, optional
`task_id`, and `created_at`.

### `activity_logs`

Audit/event records: `id`, `action`, optional `entity_type` and
`entity_id`, `user_name`, `details`, optional JSON `old_values` and
`new_values`, and `created_at`. Older installations may have started with
a smaller version of this table; initialization adds missing columns.

Audit coverage is implemented for supported task, client, project, ledger,
invoice/payment/refund, agent-run, and deliverable operations. It is not a
general-purpose immutable compliance ledger, and the operator label is not
equivalent to a separately authenticated user identity.

## Deliverable workspace tables

### `deliverables`

Stores project FK (ON DELETE RESTRICT), domain (software, design, architecture,
or feasibility), title/content, JSON sources and assumptions, generation
metadata, owner, review status, version, reviewer/review note, and timestamps.

### `deliverable_versions`

Stores immutable content snapshots per deliverable version, including project
and deliverable references, title/content, sources, assumptions, generation
metadata, owner, and creation timestamp. The pair
(`deliverable_id`, `version`) is unique.

These workspaces support drafts and internal review. They do not certify
engineering, architectural, legal, financial, or other professional outputs.

## Settings

### `settings`

Single-row UI preferences table (`id = 1`): company name, language, dark-mode
flag, and theme. Runtime settings are also read from `data/settings.json` and
environment variables; secrets should not be committed to the repository.

## Important indexes

The schema/bootstrap creates indexes for task status, role-agent assignment,
client/project links, ledger task/kind, activity-log timestamps, invoice status,
payment invoice/reference, refund payment/reference, role-agent-run task/status,
and deliverable project/domain/version lookups.

## Agent execution model

The five pipeline agents and seven role agents are separate subsystems. The
seven role agents currently produce deterministic offline plans. An optional
OpenAI provider can assist with explicitly requested draft generation; local
mode remains the default. Generated content is saved as a draft with provider
provenance and requires human review. The application does not autonomously
run shell commands, deploy software, move money, or perform external actions.

## Migration policy

All schema changes must remain additive and idempotent. Never drop/recreate a
user database to apply an upgrade. Test migrations against both a fresh
temporary database and a legacy database fixture, and verify foreign keys and
rollback behavior. Take a verified backup before significant maintenance.
