"""Accountant Agent role agent summary model."""


class AccountantAgent:
    def __init__(self):
        self.name = "Accountant Agent"
        self.role = "المحاسبة"
        self.status = "انتظار"

    def get_summary(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }
