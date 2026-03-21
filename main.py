#!/usr/bin/env python3
"""
AWS Geospatial AI Workshop — Map Builder Agent
================================================

Natural language → Aurora PostGIS query → Felt map.

Usage:
    python main.py "Show wildfire risk for buildings in Austin"
    python main.py "Map flood risk in Houston, highlight critical buildings"
    python main.py "Which Miami buildings have composite risk above 0.7?"
    python main.py   # interactive mode
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def check_env():
    """Validate required environment variables."""
    if not os.environ.get("FELT_API_TOKEN"):
        print("❌ FELT_API_TOKEN not set. Get one at felt.com/account/integrations")
        sys.exit(1)

    if not os.environ.get("AWS_DEFAULT_REGION") and not os.environ.get("AWS_PROFILE"):
        print("❌ AWS credentials not configured (needed for Bedrock).")
        sys.exit(1)

    if not os.environ.get("AURORA_PASSWORD"):
        print("⚠️  AURORA_PASSWORD not set — using local GeoJSON fallback instead of Aurora.")
        print("   Run notebooks/05_export_aurora.py to generate local data.\n")


def ensure_data():
    """Make sure sample data exists (for fallback mode)."""
    data_path = Path(__file__).parent / "data" / "gold_building_risk.geojson"
    if not data_path.exists():
        print("📦 Generating sample risk data...")
        # Run the export script to create local data
        import subprocess
        subprocess.run([sys.executable, str(Path(__file__).parent / "notebooks" / "05_export_aurora.py")], check=True)
        print()


def main():
    check_env()
    ensure_data()

    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        print("🗺️  Map Builder Agent")
        print("=" * 50)
        print("Query building risk data and create Felt maps.\n")
        print("Examples:")
        print('  • "Show wildfire risk for buildings in Austin"')
        print('  • "Map flood risk in Houston"')
        print('  • "Create a risk map of Miami critical buildings"')
        print('  • "Which LA buildings have the highest composite risk?"')
        print()
        prompt = input("🔍 > ").strip()
        if not prompt:
            sys.exit(0)

    print(f"\n🤖 Processing: {prompt}\n")

    from agent.map_agent import create_agent

    agent = create_agent()
    result = agent(prompt)

    print(f"\n{'=' * 50}")
    print("✅ Done!")


if __name__ == "__main__":
    main()
