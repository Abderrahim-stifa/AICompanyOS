"""Shared service helpers."""
from core.logs import log_activity


class BaseService:
    def __init__(self, database):
        self.db = database

    def log(self, action, entity_type, entity_id, user_name, details=""):
        """Write an audit event to this service's configured database."""
        log_activity(
            self.db,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_name=user_name,
            details=details,
        )
