"""Token usage tracking for Agno multi-agent system.

Tracks token consumption per agent to measure token reduction vs. baseline.
"""

from typing import Dict, Any
from dataclasses import dataclass, field


@dataclass
class AgentTokenUsage:
    """Token usage for a single agent."""

    input_tokens: int = 0
    output_tokens: int = 0
    api_calls: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used by this agent."""
        return self.input_tokens + self.output_tokens


class TokenTracker:
    """Track token usage across all agents in the Agno team."""

    def __init__(self):
        """Initialize token tracker."""
        self.agent_tokens: Dict[str, AgentTokenUsage] = {
            "orchestrator": AgentTokenUsage(),
            "browser_agent": AgentTokenUsage(),
            "memory_agent": AgentTokenUsage(),
            "analysis_agent": AgentTokenUsage(),
        }
        self.baseline_tokens: int = 0

    def log_agent_call(
        self,
        agent_name: str,
        input_tokens: int,
        output_tokens: int
    ) -> None:
        """Log tokens used by an agent API call.

        Args:
            agent_name: Name of the agent
            input_tokens: Input tokens consumed
            output_tokens: Output tokens generated
        """
        if agent_name not in self.agent_tokens:
            self.agent_tokens[agent_name] = AgentTokenUsage()

        usage = self.agent_tokens[agent_name]
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        usage.api_calls += 1

    def get_total_tokens(self) -> int:
        """Get total tokens across all agents.

        Returns:
            Total token count
        """
        return sum(
            agent.total_tokens
            for agent in self.agent_tokens.values()
        )

    def get_agent_tokens(self, agent_name: str) -> AgentTokenUsage:
        """Get token usage for a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentTokenUsage for the agent
        """
        return self.agent_tokens.get(agent_name, AgentTokenUsage())

    def set_baseline(self, baseline_tokens: int) -> None:
        """Set baseline token count for comparison.

        Args:
            baseline_tokens: Token count from monolithic implementation
        """
        self.baseline_tokens = baseline_tokens

    def compare_to_baseline(self) -> Dict[str, Any]:
        """Compare current token usage to baseline.

        Returns:
            Dictionary with comparison metrics
        """
        total = self.get_total_tokens()

        if self.baseline_tokens == 0:
            return {
                "total": total,
                "baseline": 0,
                "savings": 0,
                "savings_pct": 0.0
            }

        savings = self.baseline_tokens - total
        savings_pct = (savings / self.baseline_tokens) * 100

        return {
            "total": total,
            "baseline": self.baseline_tokens,
            "savings": savings,
            "savings_pct": savings_pct
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive token usage summary.

        Returns:
            Dictionary with token usage breakdown
        """
        summary = {
            "total_tokens": self.get_total_tokens(),
            "agents": {}
        }

        for agent_name, usage in self.agent_tokens.items():
            if usage.total_tokens > 0:  # Only include agents that were used
                summary["agents"][agent_name] = {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "api_calls": usage.api_calls
                }

        # Add baseline comparison if set
        if self.baseline_tokens > 0:
            summary["baseline_comparison"] = self.compare_to_baseline()

        return summary


__all__ = ["TokenTracker", "AgentTokenUsage"]
