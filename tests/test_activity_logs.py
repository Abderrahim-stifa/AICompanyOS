"""Activity logger adapter integration tests."""
from core.logs import DatabaseActivityLogger


def test_create_activity_log(temp_db):
    logger = DatabaseActivityLogger(temp_db)
    logger.log("CREATE", "TASK", 42, "Admin", "New task")

    event = temp_db.list_system_logs()[0]
    assert event["action"] == "CREATE"
    assert event["entity_type"] == "TASK"
    assert event["entity_id"] == 42
    assert event["user_name"] == "Admin"
    assert event["details"] == "New task"


def test_activity_log_preserves_delete_action(temp_db):
    logger = DatabaseActivityLogger(temp_db)
    logger.log("DELETE", "TASK", 7, "Operator", "Removed task")

    event = temp_db.list_system_logs()[0]
    assert event["action"] == "DELETE"
    assert event["details"] == "Removed task"
