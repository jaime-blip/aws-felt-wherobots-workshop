#!/usr/bin/env python3
"""
AWS Geospatial AI Workshop — Demo CLI
=======================================

Natural language interface to the climate risk agent.
Ask it about flood risk, wildfire exposure, weather forecasts,
and it'll analyze the data and create interactive Felt maps.

Usage:
    python main.py "Show me wildfire risk for buildings in LA"
    python main.py "What's the flood risk in Houston with this week's forecast?"
    python main.py "Create a climate risk map of Miami"
    python main.py   # interactive mode
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def check_env():
    """Check required environment variables."""
    missing = []
    if not os.environ.get("FELT_API_TOKEN"):
        missing.append("FELT_API_TOKEN")
    if not os.environ.get("AWS_DEFAULT_REGION") and not os.environ.get("AWS_PROFILE"):
        missing.append("AWS credentials (AWS_PROFILE or AWS_ACCESS_KEY_ID)")

    # Wherobots is optional (agent can work without it using pre-computed data)
    if not os.environ.get("WHEROBOTS_API_KEY"):
        print("⚠️  WHEROBOTS_API_KEY not set — Wherobots live queries disabled.")
        print("   Pre-computed risk data (Houston/LA/Miami) is still available.\n")

    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   • {var}")
        print("\nCopy .env.example to .env and fill in your credentials.")
        sys.exit(1)


def ensure_data():
    """Ensure sample data exists."""
    data_path = Path(__file__).parent / "data" / "risk_scored_buildings.geojson"
    if not data_path.exists():
        print("📦 Generating sample risk data (first run)...")
        exec(open(Path(__file__).parent / "notebooks" / "05_export_results.py").read())
        print()


def main():
    check_env()
    ensure_data()

    # Get prompt
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        print("🌍 Climate Risk Agent")
        print("=" * 50)
        print("Ask about climate risks for any location.")
        print()
        print("Examples:")
        print('  • "Show me wildfire risk for buildings in LA"')
        print('  • "What\'s the flood risk in Houston?"')
        print('  • "Create a climate risk map of Miami with weather forecast"')
        print('  • "What\'s the weather outlook for 29.76, -95.37?"')
        print()
        prompt = input("🔍 > ").strip()
        if not prompt:
            print("No prompt. Exiting.")
            sys.exit(0)

    print(f"\n🤖 Analyzing: {prompt}\n")

    from agent.climate_agent import create_agent

    agent = create_agent()
    result = agent(prompt)

    print(f"\n{'=' * 50}")
    print("✅ Done!")


if __name__ == "__main__":
    main()
