"""Regression tests for task-to-client/project relationships and SQLite migration."""
import sqlite3

import pytest

from core.database import Database
from core.services.task_service import TaskService


def _database(tmp_path):
    db = Database(str(tmp_path / "relationships.sqlite3"))
    db.init()
    return db


def _task_data(**extra):
    return {
        "title": "Linked task",
        "description": "Relationship test",
        "source": "test",
        "category": "general",
        "price": 100,
        "currency": "MAD",
        "priority": "normal",
        **extra,
    }


def test_fresh_database_supports_optional_task_relationships(tmp_path):
    db = _database(tmp_path)
    service = TaskService(db, default_currency="MAD")
    task = service.create_task(_task_data())

    assert task["client_id"] is None
    assert task["project_id"] is None


def test_task_can_link_client_and_project_independently(tmp_path):
    db = _database(tmp_path)
    client = db.add_client({"name": "Client A", "email": "", "phone": ""})
    project = db.add_project({
        "name": "Project A", "client_id": client["id"], "status": "new",
        "budget": 500, "currency": "MAD",
    })
    task = TaskService(db, default_currency="MAD").create_task(
        _task_data(client_id=client["id"], project_id=project["id"])
    )

    assert task["client_id"] == client["id"]
    assert task["project_id"] == project["id"]


def test_invalid_client_or_project_ids_are_rejected_on_create(tmp_path):
    db = _database(tmp_path)
    service = TaskService(db, default_currency="MAD")

    with pytest.raises(LookupError, match="client"):
        service.create_task(_task_data(client_id=9999))
    with pytest.raises(LookupError, match="project"):
        service.create_task(_task_data(project_id=9999))


def test_task_relationships_can_be_changed_and_unlinked(tmp_path):
    db = _database(tmp_path)
    client_a = db.add_client({"name": "A", "email": "", "phone": ""})
    client_b = db.add_client({"name": "B", "email": "", "phone": ""})
    service = TaskService(db, default_currency="MAD")
    task = service.create_task(_task_data(client_id=client_a["id"]))

    updated = service.update_task(task["id"], {"client_id": client_b["id"]})
    assert updated["client_id"] == client_b["id"]

    unlinked = service.update_task(task["id"], {"client_id": None})
    assert unlinked["client_id"] is None


def test_deleting_client_or_project_unlinks_task_without_deleting_it(tmp_path):
    db = _database(tmp_path)
    client = db.add_client({"name": "Client A", "email": "", "phone": ""})
    project = db.add_project({
        "name": "Project A", "client_id": client["id"], "status": "new",
        "budget": 0, "currency": "MAD",
    })
    task = TaskService(db, default_currency="MAD").create_task(
        _task_data(client_id=client["id"], project_id=project["id"])
    )

    db.delete_client(client["id"])
    after_client_delete = db.get_task(task["id"])
    assert after_client_delete["client_id"] is None
    assert after_client_delete["project_id"] == project["id"]

    db.delete_project(project["id"])
    after_project_delete = db.get_task(task["id"])
    assert after_project_delete["project_id"] is None
    assert after_project_delete["id"] == task["id"]


def test_legacy_database_migration_preserves_existing_tasks(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT '',
            price REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'USD',
            status TEXT NOT NULL DEFAULT 'found',
            agent TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute(
        """INSERT INTO tasks
           (title, description, source, category, price, currency, status, agent, created_at, updated_at)
           VALUES ('Legacy task', 'Old description', 'legacy', 'general', 25, 'MAD',
                   'found', 'manager', '2024-01-01', '2024-01-01')"""
    )
    conn.commit()
    conn.close()

    db = Database(str(path))
    db.init()
    db.init()  # migration must be idempotent
    task = db.get_task(1)

    assert task["title"] == "Legacy task"
    assert task["description"] == "Old description"
    assert task["agent"] == "manager"
    assert task["client_id"] is None
    assert task["project_id"] is None
