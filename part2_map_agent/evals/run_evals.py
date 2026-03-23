#!/usr/bin/env python3
"""
Main entry point for running skill evaluations.

Usage:
    python evals/run_evals.py                                    # Run all scenarios for all skills
    python evals/run_evals.py --skill felt-map-maker             # Run all scenarios for a specific skill
    python evals/run_evals.py --skill felt-map-maker --scenario simple-point  # Run specific scenario
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table


from judge import judge_all_results, all_criteria_passed, count_criteria_passed
from runner import run_all_scenarios, get_all_skills, get_skill_dir


console = Console()


def save_results(results: list[dict], output_dir: Path) -> None:
    """Save results to timestamped directory with iteration support."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save individual scenario results
    for result in results:
        scenario_id = result.get("scenario_id", "unknown")
        skill_name = result.get("skill_name", "")
        # Prefix scenario dir with skill name for multi-skill runs
        dir_name = f"{skill_name}/{scenario_id}" if skill_name else scenario_id
        scenario_dir = output_dir / dir_name
        scenario_dir.mkdir(parents=True, exist_ok=True)

        # Handle error scenarios
        if "error" in result and "iterations" not in result:
            error_result = {"error": result["error"]}
            error_file = scenario_dir / "error.json"
            with open(error_file, "w") as f:
                json.dump(error_result, f, indent=2)
            continue

        # Save individual iterations
        if "iterations" in result:
            for iteration in result["iterations"]:
                iteration_num = iteration.get("iteration", 1)
                iteration_dir = scenario_dir / f"iteration_{iteration_num}"
                iteration_dir.mkdir(parents=True, exist_ok=True)

                # Save actual output as separate file if present
                if actual_output := iteration.get("actual_output"):
                    # Strip markdown code blocks
                    if actual_output.startswith("```") and actual_output.endswith("```"):
                        lines = actual_output.strip().split("\n")
                        actual_output = "\n".join(lines[1:-1])

                    # Determine file extension
                    output_type = result.get("scenario_json", {}).get("output_type", "").lower()
                    if output_type == "python":
                        ext = ".py"
                    elif output_type == "fsl":
                        ext = ".json"
                    else:
                        ext = ".txt"
                    output_file = iteration_dir / f"output{ext}"

                    output_file.write_text(actual_output)

                # Create clean iteration result
                clean_iteration = {
                    "iteration": iteration_num,
                    "latency_ms": iteration.get("latency_ms"),
                    "tokens": iteration.get("tokens"),
                }

                # Add optional fields
                if judge_result := iteration.get("judge_result"):
                    clean_iteration["judge_result"] = judge_result
                if error := iteration.get("error"):
                    clean_iteration["error"] = error

                evaluation_file = iteration_dir / "evaluation.json"
                evaluation_file.write_text(json.dumps(clean_iteration, indent=2))

            # Save scenario summary
            if summary := result.get("summary"):
                summary_file = scenario_dir / "summary.json"
                summary_file.write_text(json.dumps(summary, indent=2))

    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "model": os.environ.get("EVAL_MODEL", "claude-sonnet-4-5-20250929"),
        "total_scenarios": len(results),
        "scenarios": [],
    }

    all_scores = []
    total_gen_input_tokens = 0
    total_gen_output_tokens = 0
    total_judge_input_tokens = 0
    total_judge_output_tokens = 0

    for result in results:
        scenario_summary = {"id": result.get("scenario_id")}
        if skill_name := result.get("skill_name"):
            scenario_summary["skill"] = skill_name

        if "error" in result and "iterations" not in result:
            scenario_summary["error"] = result["error"]
        elif "summary" in result:
            scenario_summary.update(result["summary"])

            # Accumulate token counts
            total_gen_input_tokens += result["summary"].get("total_input_tokens", 0)
            total_gen_output_tokens += result["summary"].get("total_output_tokens", 0)
            total_judge_input_tokens += result["summary"].get("total_judge_input_tokens", 0)
            total_judge_output_tokens += result["summary"].get("total_judge_output_tokens", 0)

            # Collect scores from iterations with judge results
            if "iterations" in result:
                scenario_scores = []
                for iteration in result["iterations"]:
                    if "judge_result" in iteration and "score" in iteration["judge_result"]:
                        score = iteration["judge_result"]["score"]
                        scenario_scores.append(score)
                        all_scores.append(score)

                if scenario_scores:
                    scenario_summary["avg_score"] = sum(scenario_scores) / len(scenario_scores)
                    scenario_summary["min_score"] = min(scenario_scores)
                    scenario_summary["max_score"] = max(scenario_scores)
                    scenario_summary["score_std_dev"] = (
                        sum((s - scenario_summary["avg_score"]) ** 2 for s in scenario_scores) / len(scenario_scores)
                    ) ** 0.5

        summary["scenarios"].append(scenario_summary)

    # Overall statistics
    if all_scores:
        summary["overall_avg_score"] = sum(all_scores) / len(all_scores)
        summary["overall_min_score"] = min(all_scores)
        summary["overall_max_score"] = max(all_scores)

    # Add token statistics
    summary["total_generation_input_tokens"] = total_gen_input_tokens
    summary["total_generation_output_tokens"] = total_gen_output_tokens
    summary["total_judge_input_tokens"] = total_judge_input_tokens
    summary["total_judge_output_tokens"] = total_judge_output_tokens
    summary["total_tokens"] = total_gen_input_tokens + total_gen_output_tokens + total_judge_input_tokens + total_judge_output_tokens

    summary_file = output_dir / "summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))


def print_results_table(results: list[dict], timestamp: str = None) -> bool:
    """Print results as a formatted table with iteration support.

    Returns:
        True if there were any failures, False if all passed
    """
    title = "Evaluation Results"
    if timestamp:
        title += f" ({timestamp})"
    table = Table(title=title)

    table.add_column("Skill", style="white", width=18)
    table.add_column("Scenario", style="cyan", width=30)
    table.add_column("Score", style="magenta")
    table.add_column("Criteria", style="white")
    table.add_column("Avg Latency", style="yellow")
    table.add_column("Gen Tok", style="blue")
    table.add_column("Judge Tok", style="blue")
    table.add_column("Cache", style="blue")
    table.add_column("Status", style="green")

    has_failures = False

    for result in results:
        scenario_id = result.get("scenario_id", "unknown")
        skill_name = result.get("skill_name", "")

        if "error" in result and "iterations" not in result:
            has_failures = True
            table.add_row(
                skill_name,
                scenario_id,
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                f"[red]ERROR: {result['error']}[/red]",
            )
            continue

        summary = result.get("summary", {})

        # Extract scores from iterations
        scores = [
            iteration["judge_result"]["score"]
            for iteration in result.get("iterations", [])
            if "judge_result" in iteration and "score" in iteration["judge_result"]
        ]

        # Format display values
        avg_score = f"{sum(scores) / len(scores):.0f}%" if scores else "-"
        avg_latency = f"{summary.get('avg_latency_ms', 0):.0f}ms"

        # Build generation tokens string (total)
        total_gen_input = summary.get('total_input_tokens', 0)
        total_gen_output = summary.get('total_output_tokens', 0)
        gen_tokens = f"{total_gen_input:.0f}/{total_gen_output:.0f}"

        # Build judge tokens string (total)
        total_judge_input = summary.get('total_judge_input_tokens', 0)
        total_judge_output = summary.get('total_judge_output_tokens', 0)
        judge_tokens = f"{total_judge_input:.0f}/{total_judge_output:.0f}" if total_judge_input > 0 else "-"

        # Build cache string
        total_cache_creation = summary.get('total_cache_creation_tokens', 0)
        total_cache_read = summary.get('total_cache_read_tokens', 0)

        cache = "-"
        if total_cache_creation > 0:
            cache = f"[yellow]Write: {total_cache_creation:.0f}[/]"
        elif total_cache_read > 0:
            cache = f"[green]Read: {total_cache_read:.0f}[/]"

        # Criteria - aggregate across all iterations
        total_passed = 0
        total_criteria = 0
        for iteration in result.get("iterations", []):
            if "judge_result" in iteration and "error" not in iteration:
                criteria = iteration["judge_result"].get("criteria", [])
                passed, total = count_criteria_passed(criteria)
                total_passed += passed
                total_criteria += total

        if total_criteria > 0:
            if total_passed == total_criteria:
                criteria_str = f"[green]{total_passed}/{total_criteria}[/green]"
            else:
                criteria_str = f"[red]{total_passed}/{total_criteria}[/red]"
        else:
            criteria_str = "-"

        # Status - check if all iterations passed (no errors + all criteria passed)
        all_passed = True
        for iteration in result.get("iterations", []):
            if "error" in iteration:
                all_passed = False
                break
            if "judge_result" in iteration:
                criteria = iteration["judge_result"].get("criteria", [])
                if not all_criteria_passed(criteria):
                    all_passed = False
                    break

        status = "[green]✓[/green]" if all_passed else "[red]✗[/red]"
        if not all_passed:
            has_failures = True

        table.add_row(skill_name, scenario_id, avg_score, criteria_str, avg_latency, gen_tokens, judge_tokens, cache, status)

    console.print(table)
    return has_failures


def run_skill_scenarios(
    skill_name: str,
    model: str,
    scenario_filter: list[str] | None = None,
    iterations: int | None = None,
) -> list[dict]:
    """Run scenarios for a specific skill, tagging results with the skill name."""
    skill_dir = get_skill_dir(skill_name)
    skill_path = skill_dir / "SKILL.md"
    scenarios_dir = skill_dir / "scenarios"

    if not skill_path.exists():
        console.print(f"[red]Skill '{skill_name}' not found at {skill_dir}[/red]")
        return []

    if not scenarios_dir.exists():
        console.print(f"[yellow]No scenarios found for skill '{skill_name}'[/yellow]")
        return []

    results = run_all_scenarios(
        scenarios_dir=scenarios_dir,
        skill_path=skill_path,
        model=model,
        scenario_filter=scenario_filter,
        iterations=iterations,
    )

    # Tag each result with the skill name
    for result in results:
        result["skill_name"] = skill_name

    return results


def main():
    parser = argparse.ArgumentParser(description="Run skill evaluations")
    parser.add_argument(
        "--skill",
        help="Run scenarios for a specific skill (default: all skills)",
    )
    parser.add_argument(
        "--scenario",
        help="Run specific scenario(s) (supports glob patterns like 'simple-*')",
    )

    parser.add_argument(
        "--model",
        default=os.environ.get("EVAL_MODEL", "claude-sonnet-4-5-20250929"),
        help="Model to use for evaluation",
    )
    parser.add_argument(
        "--judge-model",
        default=os.environ.get("JUDGE_MODEL", "claude-sonnet-4-5-20250929"),
        help="Model to use for judging",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Number of iterations to run per scenario (default: 1)",
    )

    args = parser.parse_args()

    # Check for credentials (Bedrock via AWS creds, or Anthropic API key)
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("AWS_ACCESS_KEY_ID"):
        # Try default AWS credential chain (profile, instance role, etc.)
        try:
            import boto3
            boto3.client("sts").get_caller_identity()
        except Exception:
            console.print(
                "[red]Error: No LLM credentials found.[/red]"
            )
            console.print("\nEither set ANTHROPIC_API_KEY or configure AWS credentials for Bedrock:")
            console.print("  export ANTHROPIC_API_KEY=your-key-here")
            console.print("  # or")
            console.print("  aws configure")
            sys.exit(1)

    # Determine which skills to run
    if args.skill:
        skill_names = [args.skill]
    else:
        skill_names = get_all_skills()
        if not skill_names:
            console.print("[red]No skills found in skills/ directory[/red]")
            sys.exit(1)

    console.print(f"[bold]Running evaluations with model: {args.model}[/bold]")
    console.print(f"[bold]Skills: {', '.join(skill_names)}[/bold]\n")

    # Build scenario filter
    scenario_filter = None
    if args.scenario:
        from glob import glob as glob_match

        # We'll resolve the filter per-skill in run_skill_scenarios
        # For now, just pass the pattern to filter by name
        scenario_filter_pattern = args.scenario
    else:
        scenario_filter_pattern = None

    # Run scenarios for each skill
    all_results = []
    for skill_name in skill_names:
        console.print(f"[bold cyan]Skill: {skill_name}[/bold cyan]")

        # Resolve scenario filter for this skill
        if scenario_filter_pattern:
            skill_dir = get_skill_dir(skill_name)
            scenarios_dir = skill_dir / "scenarios"

            from glob import glob as glob_match
            scenario_pattern = str(scenarios_dir / scenario_filter_pattern)
            scenario_paths = [Path(p) for p in glob_match(scenario_pattern) if Path(p).is_dir()]

            if not scenario_paths:
                console.print(f"[yellow]No scenarios matching '{scenario_filter_pattern}' in {skill_name}[/yellow]")
                continue

            scenario_ids = [p.name for p in scenario_paths]
            console.print(f"Running {len(scenario_paths)} scenario(s) > ", end="")
        else:
            scenario_ids = None
            console.print("Running all scenarios > ", end="")

        results = run_skill_scenarios(
            skill_name=skill_name,
            model=args.model,
            scenario_filter=scenario_ids,
            iterations=args.iterations,
        )
        all_results.extend(results)

    if not all_results:
        console.print("[red]No scenarios were run[/red]")
        sys.exit(1)

    # Judge results
    console.print("\n[bold]Judging results > [/bold]", end="")
    all_results = judge_all_results(all_results, model=args.judge_model)

    # Save results
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = Path("results") / timestamp
    save_results(all_results, output_dir)

    # Print summary and get pass/fail status
    has_failures = print_results_table(all_results, timestamp)

    if has_failures:
        console.print("\n[red]✗ Some evaluations failed[/red]")
        sys.exit(1)
    else:
        console.print("\n[green]✓ All evaluations passed[/green]")
        sys.exit(0)


if __name__ == "__main__":
    main()
