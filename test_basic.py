#!/usr/bin/env python3
"""Basic test of Computer Use Automation."""

import os
from dotenv import load_dotenv

from cua import ComputerUseAgent, ClaudeProvider

# Load environment variables
load_dotenv()

def test_basic_navigation():
    """Test basic navigation and screenshot."""
    print("Testing basic navigation with Claude...")

    # Get API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file")
        return False

    # Initialize provider
    provider = ClaudeProvider(api_key=api_key, model="claude-sonnet-4-5")

    # Initialize agent
    agent = ComputerUseAgent(
        provider=provider,
        display_width=1280,
        display_height=720,
        headless=True
    )

    # Run simple task
    result = agent.run_task(
        url="https://example.com",
        prompt="Take a screenshot of the page and describe what you see.",
        max_iterations=5
    )

    # Display results
    print(f"\n{'='*50}")
    print(f"Test Results:")
    print(f"  Success: {result.success}")
    print(f"  Iterations: {result.iterations}")
    print(f"  Total time: {result.total_time:.2f}s")
    if result.final_url:
        print(f"  Final URL: {result.final_url}")
    if result.error:
        print(f"  Error: {result.error}")
    print(f"{'='*50}\n")

    return result.success

if __name__ == "__main__":
    success = test_basic_navigation()
    exit(0 if success else 1)
