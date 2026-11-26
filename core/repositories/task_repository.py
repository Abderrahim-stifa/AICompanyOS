"""Task persistence adapter over the application's SQLite Database.

Database owns the transaction boundary and writes audit events atomically with
CRUD mutations. This adapter deliberately does not open a second connection.
"""


class TaskRepository:
    def __init__(self, database):
        self.database = database

    def create(self, data, user_name="Admin"):
        return self.database.add_task(data, user_name=user_name)

    def update(self, task_id, data, user_name="Admin"):
        return self.database.update_task(task_id, user_name=user_name, **data)

    def delete(self, task_id, user_name="Admin"):
        return self.database.delete_task(task_id, user_name=user_name)

    def get_by_id(self, task_id):
        return self.database.get_task(task_id)

    def list(self, status=None):
        return self.database.list_tasks(status)
