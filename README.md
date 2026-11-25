# AICompanyOS

Free Open Source AI Business Operating System.

An Arabic (RTL) dashboard to run a small company of AI agents with a human supervisor:
clients, projects, tasks, accounting, backups. SQLite storage, no paid services.

## Run the dashboard

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open http://localhost:8501. Use **الإعدادات → إدخال بيانات تجريبية** to load demo data.

Pages: لوحة التحكم (dashboard with Plotly charts) · الوكلاء · العملاء · المشاريع · المهام · الحسابات · الإعدادات (backup, demo data).

## Command line and JSON API (no extra packages)

```bash
python cli.py init
python cli.py add-task "Translate 500 words" --price 5 --source khamsat
python cli.py set-status 1 classified --category translation --agent classifier
python cli.py ledger income 5 --task 1 --note "client payment"
python cli.py summary
python cli.py backup
python cli.py serve          # JSON API on http://127.0.0.1:8000
```

## Task lifecycle

`found` → `classified` → `assigned` → `in_progress` → `done` (or `rejected`)

Default agents: manager, finder, classifier, executor, accountant.

## Layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit dashboard |
| `cli.py` | Command line and HTTP API |
| `core/service.py` | Business logic shared by the dashboard, CLI and API |
| `core/database.py` | SQLite: clients, projects, tasks, agents, ledger |
| `core/validator.py` | Input validation |
| `core/settings.py` | Settings (defaults, `data/settings.json`, `AICOS_*` env vars) |
| `core/logs.py` | Console and rotating file logs |
| `core/backup.py` | Safe backup, pruning and restore |
| `.streamlit/config.toml` | Dark theme |

## HTTP API (`python cli.py serve`)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET / POST | `/tasks` | List (`?status=done`) or create a task |
| GET / PATCH | `/tasks/<id>` | Read or update `status`, `category`, `agent` |
| GET | `/agents` | List agents |
| GET / POST | `/ledger` | List or record income/expense |
| GET | `/summary` | Totals per currency and task counts |

The server listens on `127.0.0.1` only. To expose it, set `AICOS_API_KEY`; clients then send it
in the `X-API-Key` header. The server refuses to bind to a public address without a key.

## Settings

Environment variables override `data/settings.json`: `AICOS_DATA_DIR`, `AICOS_PORT`, `AICOS_HOST`,
`AICOS_DB_PATH`, `AICOS_DEFAULT_CURRENCY`, `AICOS_API_KEY`, `AICOS_BACKUP_KEEP`, `AICOS_LOG_LEVEL`.

## License

Open source, free to use.
