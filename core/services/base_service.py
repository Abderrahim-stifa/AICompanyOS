"""Shared service helpers with an injectable activity logger."""
from core.logs import DatabaseActivityLogger


class BaseService:
    def __init__(self, database=None, activity_logger=None):
        self.db = database
        self.activity_logger = activity_logger or (
            DatabaseActivityLogger(database) if database is not None else None
        )

    def log(self, action, entity_type, entity_id, user_name, details=""):
        if self.activity_logger is None:
            raise RuntimeError("activity logger is not configured")
        return self.activity_logger.log(
            action=action, entity_type=entity_type, entity_id=entity_id,
            user_name=user_name, details=details,
        )
