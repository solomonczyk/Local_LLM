"""
Orchestrator - управление агентами
"""
from .agent import Agent
from .consilium import Consilium, get_consilium
from .orchestrator import Orchestrator, get_orchestrator

__all__ = ["Agent", "Orchestrator", "get_orchestrator", "Consilium", "get_consilium"]
