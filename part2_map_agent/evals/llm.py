"""
LLM client abstraction — uses Bedrock by default, falls back to Anthropic if ANTHROPIC_API_KEY is set.
"""

import os
import time
from typing import Any

# Model mapping: short names → Bedrock model IDs
BEDROCK_MODELS = {
    "claude-sonnet-4-5-20250929": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-sonnet-4-20250514": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "claude-opus-4-20250514": "us.anthropic.claude-opus-4-20250514-v1:0",
    "claude-haiku-3-5-20241022": "us.anthropic.claude-3-5-haiku-20241022-v1:0",
}


def _get_bedrock_model_id(model: str) -> str:
    """Map short model name to Bedrock model ID."""
    if model in BEDROCK_MODELS:
        return BEDROCK_MODELS[model]
    # Already a full Bedrock ID
    if "anthropic." in model:
        return model
    # Default
    return "us.anthropic.claude-sonnet-4-20250514-v1:0"


def call_llm(
    model: str,
    messages: list[dict],
    system: str = None,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Call an LLM and return the response.

    Uses Bedrock by default. Set ANTHROPIC_API_KEY to use Anthropic directly.

    Args:
        model: Model name (short or full Bedrock ID).
        messages: List of {"role": "user"/"assistant", "content": "..."} dicts.
        system: Optional system prompt string.
        max_tokens: Max output tokens.

    Returns:
        dict with keys: text, input_tokens, output_tokens, latency_ms,
        cache_creation_tokens, cache_read_tokens.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _call_anthropic(model, messages, system, max_tokens)
    else:
        return _call_bedrock(model, messages, system, max_tokens)


def _call_bedrock(
    model: str,
    messages: list[dict],
    system: str = None,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call via Bedrock converse API."""
    import boto3

    region = os.environ.get("AWS_REGION", "us-east-1")
    client = boto3.client("bedrock-runtime", region_name=region)
    model_id = _get_bedrock_model_id(model)

    # Build converse params
    bedrock_messages = []
    for msg in messages:
        bedrock_messages.append({
            "role": msg["role"],
            "content": [{"text": msg["content"]}],
        })

    params = {
        "modelId": model_id,
        "messages": bedrock_messages,
        "inferenceConfig": {"maxTokens": max_tokens},
    }

    if system:
        params["system"] = [{"text": system}]

    start_time = time.time()
    response = client.converse(**params)
    latency_ms = int((time.time() - start_time) * 1000)

    # Extract text
    text = ""
    for block in response.get("output", {}).get("message", {}).get("content", []):
        if "text" in block:
            text += block["text"]

    usage = response.get("usage", {})

    return {
        "text": text,
        "input_tokens": usage.get("inputTokens", 0),
        "output_tokens": usage.get("outputTokens", 0),
        "latency_ms": latency_ms,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
    }


def _call_anthropic(
    model: str,
    messages: list[dict],
    system: str = None,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Call via Anthropic API directly."""
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    params = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
    }

    if system:
        params["system"] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]

    start_time = time.time()
    response = client.messages.create(**params)
    latency_ms = int((time.time() - start_time) * 1000)

    text = ""
    for block in response.content:
        if hasattr(block, "text"):
            text += block.text

    return {
        "text": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "latency_ms": latency_ms,
        "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
    }
