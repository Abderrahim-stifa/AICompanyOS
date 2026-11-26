"""Engineer Agent role agent summary model."""


class EngineerAgent:
    def __init__(self):
        self.name = "Engineer Agent"
        self.role = "المهندس"
        self.status = "نشط"

    def get_summary(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }
