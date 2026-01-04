"""
Orchestrator - управление агентами
"""
from .agent import Agent
from .orchestrator import Orchestrator, get_orchestrator
from .consilium import Consilium, get_consilium

__all__ = ["Agent", "Orchestrator", "get_orchestrator", "Consilium", "get_consilium"]
