#!/usr/bin/env python3
"""Minimal test of Agno + Bedrock integration."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from agno.agent import Agent

# Use our model configuration that handles AWS_BEARER_TOKEN_BEDROCK
from cua.agno_config.models import get_bedrock_model

# Load .env file
load_dotenv()

# Check credentials
print("=== AWS Credentials Check ===")
print(f"AWS_REGION: {os.getenv('AWS_REGION', 'us-east-1')}")
print(f"AWS_BEARER_TOKEN_BEDROCK: {'set' if os.getenv('AWS_BEARER_TOKEN_BEDROCK') else 'not set'}")
print(f"AWS_SESSION_TOKEN: {'set' if os.getenv('AWS_SESSION_TOKEN') else 'not set'}")
print(f"AWS_ACCESS_KEY_ID: {'set' if os.getenv('AWS_ACCESS_KEY_ID') else 'not set'}")
print(f"AWS_SECRET_ACCESS_KEY: {'set' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'not set'}")

async def test_basic_agent():
    """Test basic agent without any tools."""
    print("\n=== Testing Basic Agno Agent with Bedrock ===\n")

    # Use our model getter which handles token mapping
    model = get_bedrock_model("haiku")
    print(f"✓ Created Bedrock model: {model.id}")
    print(f"  Region: {model.aws_region}")

    # Create simple agent (no tools)
    agent = Agent(
        name="Test Agent",
        model=model,
        description="Simple test agent",
        instructions="You are a helpful assistant. Answer questions concisely.",
        markdown=True
    )
    print("✓ Created agent")

    # Try to run agent
    print("\n--- Sending request to agent ---")
    try:
        response = await agent.arun("What is 2+2? Answer in one word.")
        print(f"\n✓ Agent response: {response}")

        # Check if response contains error
        if hasattr(response, 'content') and 'Error' in str(response.content):
            print(f"\n⚠ Response contains error: {response.content}")
            return False

        return True
    except Exception as e:
        print(f"\n✗ Agent failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_basic_agent())
    if success:
        print("\n=== ✓ Basic Agno + Bedrock integration works ===")
    else:
        print("\n=== ✗ Basic Agno + Bedrock integration failed ===")
