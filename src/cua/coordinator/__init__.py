"""Coordinator agent for simplified MCP multi-agent architecture."""

from cua.coordinator.agent import CoordinatorAgent
from cua.coordinator.facts_tracker import CriticalFactsTracker

__all__ = [
    "CoordinatorAgent",
    "CriticalFactsTracker",
]
