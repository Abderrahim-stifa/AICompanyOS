"""Shared pytest fixtures using the application's real SQLite schema."""
import pytest

from core.database import Database


@pytest.fixture
def temp_db(tmp_path):
    database = Database(str(tmp_path / "test-company.sqlite3"))
    database.init()
    return database


@pytest.fixture
def sample_task(temp_db):
    return temp_db.add_task({
        "title": "Sample Task",
        "description": "Fixture task",
        "source": "pytest",
        "category": "test",
        "price": 0,
        "currency": "MAD",
        "priority": "normal",
    })
