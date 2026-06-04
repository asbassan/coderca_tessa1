"""
Tessa1 - Feed retrieval harness demo built from the CodeRCA architecture.
"""

from .agent_selector import AgentSelector, AgentScore
from .copilot_client import CopilotClient, LLMResponse, create_client
from .agents import BaseAgent, DatabaseAgent, CatalogAgent, OrderAgent, BasketAgent
from .input_loader import FeedInputLoader
from .orchestrator import Orchestrator

__version__ = "0.1.0"
__all__ = [
    "AgentSelector",
    "AgentScore",
    "CopilotClient",
    "LLMResponse",
    "create_client",
    "FeedInputLoader",
    "BaseAgent",
    "DatabaseAgent",
    "CatalogAgent",
    "OrderAgent",
    "BasketAgent",
    "Orchestrator",
]
