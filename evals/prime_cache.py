#!/usr/bin/env python3
"""
Prime the Claude API prompt cache with skill content.

This script makes a minimal API call with SKILL.md content marked for caching,
so that subsequent eval runs can benefit from cache reads instead of cache writes.

Usage:
    python evals/prime_cache.py                          # Prime cache for all skills
    python evals/prime_cache.py --skill felt-map-maker   # Prime cache for a specific skill
"""
import argparse
import os
import sys
from pathlib import Path

from anthropic import Anthropic

from runner import get_all_skills, get_skill_dir, load_skill


def prime_cache(skill_path: Path, model: str = "claude-sonnet-4-5-20250929") -> dict:
    """
    Make a minimal API call to prime the cache with the skill content.

    Returns cache metrics from the response.
    """
    skill_prompt = load_skill(skill_path)

    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=model,
        max_tokens=10,  # Minimal output needed
        system=[
            {
                "type": "text",
                "text": skill_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[{"role": "user", "content": "Ready"}],
    )

    return {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
    }


def main():
    parser = argparse.ArgumentParser(description="Prime Claude API prompt cache with skill content")
    parser.add_argument(
        "--skill",
        help="Skill to prime cache for (default: all skills)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("EVAL_MODEL", "claude-sonnet-4-5-20250929"),
        help="Model to use for cache priming (default: claude-sonnet-4-5-20250929)",
    )

    args = parser.parse_args()

    # Check for API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    # Determine which skills to prime
    if args.skill:
        skill_names = [args.skill]
    else:
        skill_names = get_all_skills()
        if not skill_names:
            print("No skills found in skills/ directory", file=sys.stderr)
            sys.exit(1)

    print(f"Priming cache with model: {args.model}")
    print(f"Skills: {', '.join(skill_names)}\n")

    for skill_name in skill_names:
        skill_dir = get_skill_dir(skill_name)
        skill_path = skill_dir / "SKILL.md"

        if not skill_path.exists():
            print(f"Warning: SKILL.md not found for '{skill_name}' at {skill_path}", file=sys.stderr)
            continue

        print(f"Priming cache for skill: {skill_name}")

        try:
            metrics = prime_cache(skill_path=skill_path, model=args.model)

            print(f"  Input tokens: {metrics['input_tokens']}")
            print(f"  Output tokens: {metrics['output_tokens']}")
            print(f"  Cache creation tokens: {metrics['cache_creation_tokens']}")
            print(f"  Cache read tokens: {metrics['cache_read_tokens']}")

            if metrics['cache_creation_tokens'] > 0:
                print(f"  Cache created with {metrics['cache_creation_tokens']} tokens")
                print(f"  Subsequent requests will read from cache (~5 min TTL)")
            elif metrics['cache_read_tokens'] > 0:
                print(f"  Cache already exists, read {metrics['cache_read_tokens']} tokens")
            else:
                print(f"  Warning: No cache tokens recorded (skill may be too small)")

            print()

        except Exception as e:
            print(f"Error priming cache for '{skill_name}': {e}", file=sys.stderr)
            sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
