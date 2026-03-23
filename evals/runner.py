"""
Test execution logic for skill evals.
"""
import json
import os
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic


RUNNER_PROMPT_TEMPLATE = """You are evaluating your knowledge based on the provided skill documentation.
{context_guidance}
User prompt: {prompt}
{data_guidance}
Output only the {output_type} code in your response. Do not include explanations or markdown code fences unless the output type requires them.{python_guidance}"""

CONTEXT_GUIDANCE_TEMPLATE = """
Previous context from map creation (output from skill.inspect_created_map):

{context_json_contents}

This context is in your context window as if you had just run inspect_created_map(). Use this information for styling decisions.
"""

DATA_GUIDANCE_TEMPLATE = """
Sample data representing layer attributes:

{data_csv_contents}

This data shows you the available attributes you can reference in your FSL styling (like "land_use", "population", etc.).
"""

PYTHON_GUIDANCE = """

IMPORTANT for Python code: If your code includes both map creation/upload steps AND styling steps, clearly separate them with a comment marking the boundary, such as:
# Stage 2: Apply styling
This helps distinguish the creation phase from the styling phase."""


def get_repo_root() -> Path:
    """Get the repository root directory."""
    return Path(__file__).parent.parent


def get_skills_root() -> Path:
    """Get the skills root directory."""
    return get_repo_root() / "part2_map_agent" / "skills"


def get_skill_dir(skill_name: str) -> Path:
    """Get the directory for a specific skill."""
    return get_skills_root() / skill_name


def get_all_skills() -> list[str]:
    """Discover all skills by scanning the skills/ directory."""
    skills_dir = get_skills_root()
    if not skills_dir.exists():
        return []
    return sorted([
        p.name for p in skills_dir.iterdir()
        if p.is_dir() and (p / "SKILL.md").exists()
    ])


def load_skill(skill_path: Path = None) -> str:
    """Load the SKILL.md file as the system prompt."""
    if skill_path is None:
        # Legacy fallback - shouldn't normally be used
        script_dir = Path(__file__).parent
        skill_path = script_dir.parent / "SKILL.md"
    return skill_path.read_text()





def load_scenario(scenario_path: Path) -> dict[str, Any]:
    """
    Load a scenario from a directory.

    Returns dict with:
        - scenario_json: parsed scenario.json
        - data_csv: contents of data.csv
        - context_json: contents of context.json (if exists)
        - reference: contents of reference.* file
        - reference_ext: file extension of reference file
    """
    scenario_json_path = scenario_path / "scenario.json"
    data_csv_path = scenario_path / "data.csv"
    context_json_path = scenario_path / "context.json"

    if not scenario_json_path.exists():
        raise FileNotFoundError(f"Missing scenario.json in {scenario_path}")

    scenario_json = json.loads(scenario_json_path.read_text())

    # Load data.csv if it exists
    data_csv = ""
    if data_csv_path.exists():
        data_csv = data_csv_path.read_text()

    # Load context.json if it exists
    context_json = ""
    if context_json_path.exists():
        context_json = context_json_path.read_text()

    # Find reference.* file (any extension)
    reference_files = list(scenario_path.glob("reference.*"))
    if not reference_files:
        raise FileNotFoundError(f"Missing reference.* file in {scenario_path}")

    reference_file = reference_files[0]
    reference = reference_file.read_text()
    reference_ext = reference_file.suffix

    return {
        "scenario_json": scenario_json,
        "data_csv": data_csv,
        "context_json": context_json,
        "reference": reference,
        "reference_ext": reference_ext,
    }


def build_user_message(
    prompt: str,
    output_type: str,
    data_csv: str,
    context_json: str = "",
) -> str:
    """Build the user message by filling in the runner prompt template."""
    # Add Python-specific guidance for two-stage workflows
    python_guidance = PYTHON_GUIDANCE if output_type.upper() == "PYTHON" else ""

    # Add context guidance if context.json exists
    if context_json and context_json.strip():
        context_guidance = CONTEXT_GUIDANCE_TEMPLATE.format(context_json_contents=context_json)
    else:
        context_guidance = ""

    # Add data guidance if data CSV exists
    if data_csv and data_csv.strip():
        data_guidance = DATA_GUIDANCE_TEMPLATE.format(data_csv_contents=data_csv)
    else:
        data_guidance = ""

    return RUNNER_PROMPT_TEMPLATE.format(
        prompt=prompt,
        output_type=output_type,
        context_guidance=context_guidance,
        data_guidance=data_guidance,
        python_guidance=python_guidance,
    )


def run_scenario(
    scenario: dict[str, Any],
    skill_prompt: str,
    model: str = "claude-sonnet-4-5-20250929",
) -> dict[str, Any]:
    """
    Run a single scenario.

    Returns:
        - actual_output: Claude's response
        - latency_ms: time taken
        - tokens: input/output token counts
    """
    scenario_json = scenario["scenario_json"]

    # Build user message
    user_message = build_user_message(
        prompt=scenario_json["prompt"],
        output_type=scenario_json["output_type"],
        data_csv=scenario["data_csv"],
        context_json=scenario.get("context_json", ""),
    )

    # Call Claude API
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    start_time = time.time()

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": skill_prompt,
                "cache_control": {"type": "ephemeral"}
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    latency_ms = int((time.time() - start_time) * 1000)

    # Extract text content
    actual_output = ""
    for block in response.content:
        if hasattr(block, "text"):
            actual_output += block.text

    # Build token info with cache metrics
    tokens_info = {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
    }

    # Add cache metrics if available
    if hasattr(response.usage, "cache_creation_input_tokens"):
        tokens_info["cache_creation"] = response.usage.cache_creation_input_tokens
    if hasattr(response.usage, "cache_read_input_tokens"):
        tokens_info["cache_read"] = response.usage.cache_read_input_tokens

    return {
        "actual_output": actual_output,
        "latency_ms": latency_ms,
        "tokens": tokens_info,
    }


def run_scenario_with_iterations(
    scenario: dict[str, Any],
    scenario_id: str,
    skill_prompt: str,
    model: str = "claude-sonnet-4-5-20250929",
    iterations: int | None = None,
) -> dict[str, Any]:
    """
    Run a scenario multiple times based on iterations config.

    Returns:
        - scenario_id: scenario identifier (from folder name)
        - iterations: list of individual iteration results
        - summary: aggregated metrics across iterations
    """
    scenario_json = scenario["scenario_json"]
    # CLI argument overrides scenario config, default to 1
    iterations_count = iterations if iterations is not None else 1

    iteration_results = []

    for i in range(iterations_count):
        try:
            result = run_scenario(
                scenario=scenario,
                skill_prompt=skill_prompt,
                model=model,
            )
            result["iteration"] = i + 1
            iteration_results.append(result)
            print("\033[32m.\033[0m", end="", flush=True)  # Green dot for success
        except Exception as e:
            error_result = {
                "iteration": i + 1,
                "error": str(e),
                "latency_ms": 0,
                "tokens": {"input": 0, "output": 0},
            }
            iteration_results.append(error_result)
            print("\033[31mx\033[0m", end="", flush=True)  # Red x for error

    print()  # Newline after completing scenario iterations

    # Generate scenario summary
    successful_results = [r for r in iteration_results if "error" not in r]

    summary = {}

    if successful_results:
        latencies = [r["latency_ms"] for r in successful_results]
        input_tokens = [r["tokens"]["input"] for r in successful_results]
        output_tokens = [r["tokens"]["output"] for r in successful_results]
        cache_creation_tokens = [r["tokens"].get("cache_creation", 0) for r in successful_results]
        cache_read_tokens = [r["tokens"].get("cache_read", 0) for r in successful_results]

        summary.update({
            "avg_latency_ms": sum(latencies) / len(latencies),
            "min_latency_ms": min(latencies),
            "max_latency_ms": max(latencies),
            "total_input_tokens": sum(input_tokens),
            "total_output_tokens": sum(output_tokens),
            "avg_input_tokens": sum(input_tokens) / len(input_tokens),
            "avg_output_tokens": sum(output_tokens) / len(output_tokens),
            "total_cache_creation_tokens": sum(cache_creation_tokens),
            "total_cache_read_tokens": sum(cache_read_tokens),
        })

    return {
        "scenario_id": scenario_id,
        "scenario_json": scenario_json,
        "reference_output": scenario["reference"],
        "reference_ext": scenario["reference_ext"],
        "iterations": iteration_results,
        "summary": summary,
    }


def run_all_scenarios(
    scenarios_dir: Path = None,
    skill_path: Path = None,
    model: str = "claude-sonnet-4-5-20250929",
    scenario_filter: list[str] = None,
    iterations: int | None = None,
) -> list[dict[str, Any]]:
    """
    Run all scenarios in the scenarios directory with multiple iterations.

    Args:
        scenarios_dir: Path to the scenarios directory.
        skill_path: Path to the SKILL.md file to use as system prompt.
        model: Model to use for evaluation.
        scenario_filter: List of scenario names to run (None = all).
        iterations: Number of iterations per scenario.

    Returns list of results, one per scenario with iteration data.
    """
    skill_prompt = load_skill(skill_path)

    if scenarios_dir is None:
        script_dir = Path(__file__).parent
        scenarios_dir = script_dir / "scenarios"

    results = []

    # Get all scenario directories (sorted)
    scenario_paths = sorted([p for p in scenarios_dir.iterdir() if p.is_dir()])

    # Filter scenarios if specified
    if scenario_filter:
        scenario_paths = [p for p in scenario_paths if p.name in scenario_filter]

    for scenario_path in scenario_paths:
        scenario_id = scenario_path.name

        try:
            # Load scenario
            scenario = load_scenario(scenario_path)

            # Run scenario with iterations
            result = run_scenario_with_iterations(
                scenario=scenario,
                scenario_id=scenario_id,
                skill_prompt=skill_prompt,
                model=model,
                iterations=iterations,
            )

            results.append(result)

        except Exception as e:
            error_result = {
                "scenario_id": scenario_id,
                "error": str(e),
            }
            results.append(error_result)

    return results
