"""Regression tests for task-to-client/project relationships and SQLite migration."""
import sqlite3

import pytest

from core.database import Database
from core.services.task_service import TaskService
from core.task_search import search_tasks


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

    # Foreign keys added by ALTER TABLE must remain active on upgraded databases.
    client = db.add_client({"name": "Migrated client", "email": "", "phone": ""})
    project = db.add_project({
        "name": "Migrated project", "client_id": client["id"], "status": "new",
        "budget": 0, "currency": "MAD",
    })
    service = TaskService(db, default_currency="MAD")
    service.update_task(1, {"client_id": client["id"], "project_id": project["id"]})
    db.delete_client(client["id"])
    assert db.get_task(1)["client_id"] is None
    assert db.get_task(1)["project_id"] == project["id"]


def test_search_matches_linked_client_and_project_names():
    tasks = [
        {"id": 1, "title": "Build site", "description": "", "client_id": 10, "project_id": 20},
        {"id": 2, "title": "Other task", "description": "", "client_id": None, "project_id": None},
    ]
    clients = [{"id": 10, "name": "Atlas Client"}]
    projects = [{"id": 20, "name": "Mobile Platform"}]

    assert [task["id"] for task in search_tasks(tasks, "Atlas", clients, projects)] == [1]
    assert [task["id"] for task in search_tasks(tasks, "Mobile", clients, projects)] == [1]


def test_invalid_relationship_update_is_rejected(tmp_path):
    db = _database(tmp_path)
    service = TaskService(db, default_currency="MAD")
    task = service.create_task(_task_data())

    with pytest.raises(ValueError, match="project"):
        service.update_task(task["id"], {"project_id": 123456})


def test_client_deletion_audits_all_detached_relationships_and_preserves_invoice_snapshot(tmp_path):
    import json

    db = _database(tmp_path)
    client = db.add_client({"name": "Audited client", "email": "", "phone": ""})
    project = db.add_project({
        "name": "Client project", "client_id": client["id"], "status": "new",
        "budget": 100, "currency": "MAD",
    })
    task = TaskService(db, default_currency="MAD").create_task(
        _task_data(client_id=client["id"], project_id=project["id"], price=500)
    )
    invoice = db.create_invoice(task["id"])

    db.delete_client(client["id"], user_name="Owner")

    assert db.get_task(task["id"])["client_id"] is None
    projects = db.list_projects()
    assert next(row for row in projects if row["id"] == project["id"])["client_id"] is None
    saved_invoice = next(row for row in db.list_invoices() if row["id"] == invoice["id"])
    assert saved_invoice["client_id"] is None
    assert saved_invoice["client_name"] == "Audited client"

    events = [row for row in db.list_system_logs() if row["action"] == "UNLINK_CLIENT"]
    assert {(row["entity_type"], row["entity_id"]) for row in events} == {
        ("TASK", task["id"]), ("PROJECT", project["id"]), ("INVOICE", invoice["id"])
    }
    for event in events:
        assert event["user_name"] == "Owner"
        assert json.loads(event["old_values"])["client_id"] == client["id"]
        assert json.loads(event["new_values"])["client_id"] is None


def test_project_deletion_audits_detached_tasks(tmp_path):
    import json

    db = _database(tmp_path)
    project = db.add_project({
        "name": "Audited project", "client_id": None, "status": "new",
        "budget": 0, "currency": "MAD",
    })
    task = TaskService(db, default_currency="MAD").create_task(
        _task_data(project_id=project["id"])
    )

    db.delete_project(project["id"], user_name="ProjectOwner")

    assert db.get_task(task["id"])["project_id"] is None
    events = [row for row in db.list_system_logs() if row["action"] == "UNLINK_PROJECT"]
    assert len(events) == 1
    assert events[0]["entity_type"] == "TASK"
    assert events[0]["entity_id"] == task["id"]
    assert events[0]["user_name"] == "ProjectOwner"
    assert json.loads(events[0]["old_values"])["project_id"] == project["id"]
    assert json.loads(events[0]["new_values"])["project_id"] is None


def test_client_delete_rolls_back_all_unlinks_and_audit_events_on_failure(tmp_path):
    db = _database(tmp_path)
    client = db.add_client({"name": "Rollback client", "email": "", "phone": ""})
    project = db.add_project({
        "name": "Rollback project", "client_id": client["id"], "status": "new",
        "budget": 0, "currency": "MAD",
    })
    task = TaskService(db, default_currency="MAD").create_task(
        _task_data(client_id=client["id"], project_id=project["id"], price=250)
    )
    invoice = db.create_invoice(task["id"])
    with db.connect() as conn:
        conn.execute("""
            CREATE TRIGGER fail_invoice_client_unlink
            BEFORE UPDATE OF client_id ON invoices
            BEGIN SELECT RAISE(ABORT, 'forced invoice unlink failure'); END
        """)

    with pytest.raises(sqlite3.IntegrityError, match="forced invoice unlink failure"):
        db.delete_client(client["id"], user_name="RollbackActor")

    assert any(row["id"] == client["id"] for row in db.list_clients())
    assert db.get_task(task["id"])["client_id"] == client["id"]
    assert next(row for row in db.list_projects() if row["id"] == project["id"])["client_id"] == client["id"]
    saved_invoice = next(row for row in db.list_invoices() if row["id"] == invoice["id"])
    assert saved_invoice["client_id"] == client["id"]
    events = db.list_system_logs()
    assert not any(
        row["action"] in {"UNLINK_CLIENT", "DELETE"}
        and row["user_name"] == "RollbackActor"
        for row in events
    )


def test_project_delete_rolls_back_unlink_and_audit_on_failure(tmp_path):
    db = _database(tmp_path)
    project = db.add_project({
        "name": "Rollback project", "client_id": None, "status": "new",
        "budget": 0, "currency": "MAD",
    })
    task = TaskService(db, default_currency="MAD").create_task(
        _task_data(project_id=project["id"])
    )
    with db.connect() as conn:
        conn.execute("""
            CREATE TRIGGER fail_task_project_unlink
            BEFORE UPDATE OF project_id ON tasks
            BEGIN SELECT RAISE(ABORT, 'forced project unlink failure'); END
        """)

    with pytest.raises(sqlite3.IntegrityError, match="forced project unlink failure"):
        db.delete_project(project["id"], user_name="RollbackActor")

    assert any(row["id"] == project["id"] for row in db.list_projects())
    assert db.get_task(task["id"])["project_id"] == project["id"]
    events = db.list_system_logs()
    assert not any(
        row["action"] in {"UNLINK_PROJECT", "DELETE"}
        and row["user_name"] == "RollbackActor"
        for row in events
    )
