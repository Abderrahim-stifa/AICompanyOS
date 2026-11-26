"""Research Agent role agent summary model."""


class ResearcherAgent:
    def __init__(self):
        self.name = "Research Agent"
        self.role = "البحث"
        self.status = "انتظار"

    def get_summary(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }
