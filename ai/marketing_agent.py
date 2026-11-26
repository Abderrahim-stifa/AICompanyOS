"""Marketing Agent role agent summary model."""


class MarketingAgent:
    def __init__(self):
        self.name = "Marketing Agent"
        self.role = "التسويق"
        self.status = "انتظار"

    def get_summary(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }
