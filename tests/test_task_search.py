"""Unit tests for global task search."""
import unittest

from core.task_search import search_tasks


class TaskSearchTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [
            {"id": 1, "title": "Prepare proposal", "description": "Website redesign", "client_id": 10},
            {"id": 2, "title": "Monthly report", "description": "Financial summary", "client_id": 20},
            {"id": 3, "title": "Translate document", "description": "Arabic to English", "client_id": None},
        ]
        self.clients = [
            {"id": 10, "name": "Acme Studio"},
            {"id": 20, "name": "Northwind"},
        ]

    def test_empty_query_returns_all_tasks(self):
        self.assertEqual(search_tasks(self.tasks, ""), self.tasks)
        self.assertEqual(search_tasks(self.tasks, "   "), self.tasks)

    def test_searches_title_case_insensitively(self):
        self.assertEqual(
            [task["id"] for task in search_tasks(self.tasks, "PROPOSAL")],
            [1],
        )

    def test_searches_description(self):
        self.assertEqual(
            [task["id"] for task in search_tasks(self.tasks, "financial")],
            [2],
        )

    def test_searches_linked_client_name(self):
        self.assertEqual(
            [task["id"] for task in search_tasks(self.tasks, "acme", self.clients)],
            [1],
        )

    def test_search_without_clients_is_safe(self):
        self.assertEqual(
            [task["id"] for task in search_tasks(self.tasks, "arabic")],
            [3],
        )


if __name__ == "__main__":
    unittest.main()
