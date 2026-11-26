"""CEO Agent role agent summary model."""


class CEOAgent:
    def __init__(self):
        self.name = "CEO Agent"
        self.role = "الرئيس التنفيذي"
        self.status = "نشط"

    def get_summary(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
        }
