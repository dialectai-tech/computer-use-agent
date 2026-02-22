"""AWS Bedrock model configuration for Agno framework.

This module provides model configuration for Claude models via AWS Bedrock.
Follows the plan directive: HAIKU ONLY by default, user controls testing.
"""

import os
from typing import Literal

from cua.agno_config.bedrock_mcp_model import BedrockMCPModel


# Model type aliases for clarity
ModelType = Literal["haiku", "sonnet"]

# Bedrock model IDs (using inference profile IDs with us. prefix)
HAIKU_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def get_bedrock_model(
    model_type: ModelType = "haiku",
    region: str | None = None
) -> BedrockMCPModel:
    """Get configured Bedrock MCP model instance.

    Args:
        model_type: Model to use - "haiku" (default) or "sonnet"
        region: AWS region (default: us-east-1 or AWS_REGION env var)

    Returns:
        Configured BedrockMCPModel instance with MCP tool support

    Note:
        Authentication uses environment variables in order:
        1. AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY
        2. AWS_BEARER_TOKEN_BEDROCK → mapped to AWS_SESSION_TOKEN
        3. IAM role (if running on EC2/ECS)
        4. ~/.aws/credentials fallback
    """
    if region is None:
        region = os.getenv("AWS_REGION", "us-east-1")

    # Map model type to Bedrock model ID
    model_id = HAIKU_MODEL_ID if model_type == "haiku" else SONNET_MODEL_ID

    # Handle AWS_BEARER_TOKEN_BEDROCK → AWS_SESSION_TOKEN mapping
    if "AWS_BEARER_TOKEN_BEDROCK" in os.environ and "AWS_SESSION_TOKEN" not in os.environ:
        os.environ["AWS_SESSION_TOKEN"] = os.environ["AWS_BEARER_TOKEN_BEDROCK"]

    # Create Bedrock MCP model (includes tool result formatting)
    return BedrockMCPModel(
        id=model_id,
        aws_region=region
    )


# Pre-configured model instances for default usage
HAIKU_MODEL = get_bedrock_model("haiku")
SONNET_MODEL = get_bedrock_model("sonnet")


__all__ = ["get_bedrock_model", "HAIKU_MODEL", "SONNET_MODEL", "ModelType"]
