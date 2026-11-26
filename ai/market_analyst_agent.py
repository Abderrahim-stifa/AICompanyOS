"""Market Analyst Agent role agent summary model."""


class MarketAnalystAgent:
    def __init__(self):
        self.name = "Market Analyst Agent"
        self.role = "تحليل السوق"
        self.status = "انتظار"

    def get_summary(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }
