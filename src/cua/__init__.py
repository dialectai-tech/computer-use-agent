"""Computer Use Automation - Multi-provider AI agent for browser automation."""

__version__ = "0.1.0"

from cua.agent.loop import ComputerUseAgent
from cua.providers.base import ComputerUseProvider
from cua.providers.claude import ClaudeProvider
from cua.providers.openai import OpenAIProvider

__all__ = [
    "ComputerUseAgent",
    "ComputerUseProvider",
    "ClaudeProvider",
    "OpenAIProvider",
]
