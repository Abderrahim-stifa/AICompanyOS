"""Public package for the seven AICompanyOS role agents."""
from .registry import AGENTS, run_agent
from .ceo_agent import CEOAgent
from .engineer_agent import EngineerAgent
from .marketing_agent import MarketingAgent
from .researcher_agent import ResearcherAgent
from .consultant_agent import ConsultantAgent
from .accountant_agent import AccountantAgent
from .market_analyst_agent import MarketAnalystAgent

AGENT_CLASSES = (
    CEOAgent,
    EngineerAgent,
    MarketingAgent,
    ResearcherAgent,
    ConsultantAgent,
    AccountantAgent,
    MarketAnalystAgent,
)

__all__ = ["AGENTS", "AGENT_CLASSES", "run_agent"]
