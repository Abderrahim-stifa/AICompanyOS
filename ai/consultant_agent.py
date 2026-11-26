"""Consultant Agent role agent summary model."""


class ConsultantAgent:
    def __init__(self):
        self.name = "Consultant Agent"
        self.role = "الاستشارات"
        self.status = "انتظار"

    def get_summary(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }
