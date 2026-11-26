"""Dependency-inversion contracts for application services and repositories."""
from abc import ABC, abstractmethod


class ITaskService(ABC):
    @abstractmethod
    def create_task(self, data, user_name="Admin"):
        raise NotImplementedError

    @abstractmethod
    def update_task(self, task_id, data, user_name="Admin"):
        raise NotImplementedError

    @abstractmethod
    def delete_task(self, task_id, user_name="Admin"):
        raise NotImplementedError


class ITaskRepository(ABC):
    @abstractmethod
    def create(self, data, user_name="Admin"):
        raise NotImplementedError

    @abstractmethod
    def update(self, task_id, data, user_name="Admin"):
        raise NotImplementedError

    @abstractmethod
    def delete(self, task_id, user_name="Admin"):
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, task_id):
        raise NotImplementedError

    @abstractmethod
    def list(self, status=None):
        raise NotImplementedError


class IActivityLogger(ABC):
    @abstractmethod
    def log(self, action, entity_type, entity_id, user_name, details="", old_values=None, new_values=None):
        raise NotImplementedError
