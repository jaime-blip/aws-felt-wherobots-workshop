"""
LLM-as-judge logic for evaluating scenario outputs.
"""
import json
import os
from typing import Any

from llm import call_llm
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table


console = Console()


def all_criteria_passed(criteria: list[dict[str, Any]]) -> bool:
    """Check if all criteria passed. Returns True if all passed, False if any failed."""
    if not criteria:
        # No criteria means we can't evaluate
        return False

    for criterion in criteria:
        if isinstance(criterion, dict):
            if not criterion.get("passed", False):
                return False
    return True


def count_criteria_passed(criteria: list[dict[str, Any]]) -> tuple[int, int]:
    """Count how many criteria passed vs total. Returns (passed_count, total_count)."""
    if not criteria:
        return (0, 0)

    total = 0
    passed = 0
    for criterion in criteria:
        if isinstance(criterion, dict):
            total += 1
            if criterion.get("passed", False):
                passed += 1

    return (passed, total)


JUDGE_PROMPT_TEMPLATE = """You are evaluating a response against a reference answer for a Felt mapping evaluation.

TASK:
{prompt}

EXPECTED OUTPUT TYPE:
{output_type}

EVALUATION CRITERIA:
{criteria}

ACTUAL OUTPUT:
```
{actual}
```

REFERENCE OUTPUT:
```
{reference}
```

Evaluate the actual output against the reference output and criteria. Provide:
1. Overall score (0-100) where 100 is perfect match
2. Detailed reasoning for the score
3. Assessment of each evaluation criterion (passed/failed with notes)
4. Specific differences from reference that matter
5. Flag any discrepancies between the reference and criteria as failures

Output your evaluation as JSON in this exact format:
{{
  "score": 85,
  "reasoning": "Detailed explanation of score...",
  "criteria": [
    {{"passed": true, "notes": "..."}},
    {{"passed": false, "notes": "..."}}
  ],
  "differences": ["difference 1", "difference 2"]
}}

Only output the JSON, nothing else.
"""


def judge_response(
    actual: str,
    reference: str,
    scenario_json: dict[str, Any],
    model: str = "claude-sonnet-4-5-20250929",
) -> dict[str, Any]:
    """
    Use Claude as a judge to evaluate actual output against reference.

    Returns:
        - score: 0-100
        - reasoning: explanation
        - criteria: dict of criterion -> {passed, notes}
        - differences: list of key differences
    """
    # Build evaluation criteria list
    criteria_list = scenario_json.get("criteria", [])
    criteria = "\n".join(
        f"{i+1}. {instruction}"
        for i, instruction in enumerate(criteria_list)
    )

    # Build judge prompt
    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
        prompt=scenario_json.get("prompt", "N/A"),
        output_type=scenario_json.get("output_type", "N/A"),
        criteria=criteria if criteria else "No specific criteria provided.",
        actual=actual,
        reference=reference,
    )

    # Call LLM (Bedrock or Anthropic)
    result = call_llm(
        model=model,
        messages=[{"role": "user", "content": judge_prompt}],
        max_tokens=4096,
    )

    judge_output = result["text"]

    judge_tokens = {
        "input": result["input_tokens"],
        "output": result["output_tokens"],
    }
    if result.get("cache_creation_tokens"):
        judge_tokens["cache_creation"] = result["cache_creation_tokens"]
    if result.get("cache_read_tokens"):
        judge_tokens["cache_read"] = result["cache_read_tokens"]

    # Parse JSON response
    try:
        # Try to find JSON in the response
        # Look for content between first { and last }
        start_idx = judge_output.find("{")
        end_idx = judge_output.rfind("}")

        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON object found in response")

        json_str = judge_output[start_idx : end_idx + 1]
        result = json.loads(json_str)

        # Add token usage to result
        result["tokens"] = judge_tokens

        return result

    except (json.JSONDecodeError, ValueError) as e:
        # If parsing fails, return error result
        return {
            "score": 0,
            "reasoning": f"Failed to parse judge output: {e}",
            "criteria": {},
            "differences": [],
            "raw_judge_output": judge_output,
            "tokens": judge_tokens,
        }


def judge_all_results(
    results: list[dict[str, Any]],
    model: str = "claude-sonnet-4-5-20250929",
) -> list[dict[str, Any]]:
    """
    Judge all scenario results with iteration support.

    Returns updated results list with judge_result added to each iteration.
    """
    judged_results = []

    for result in results:
        # Skip if there was an error at scenario level
        if "error" in result and "iterations" not in result:
            judged_results.append(result)
            continue

        scenario_id = result.get("scenario_id", "unknown")

        # Judge each iteration
        if "iterations" in result:
            for iteration in result["iterations"]:
                # Skip iterations with errors
                if "error" in iteration:
                    continue

                # Judge the iteration result
                judge_result = judge_response(
                    actual=iteration["actual_output"],
                    reference=result["reference_output"],
                    scenario_json=result["scenario_json"],
                    model=model,
                )

                # Add judge result to the iteration
                iteration["judge_result"] = judge_result

            # Update summary with judge token stats
            _update_summary_with_judge_tokens(result)

            # Print scenario results table
            print_scenario_results(scenario_id, result)

        judged_results.append(result)

    return judged_results


def _update_summary_with_judge_tokens(result: dict[str, Any]) -> None:
    """Update scenario summary with judge token statistics."""
    if "iterations" not in result or "summary" not in result:
        return

    # Collect judge tokens from successful iterations with judge results
    judge_iterations = [
        iteration for iteration in result["iterations"]
        if "error" not in iteration and "judge_result" in iteration and "tokens" in iteration["judge_result"]
    ]

    if not judge_iterations:
        return

    judge_input_tokens = [it["judge_result"]["tokens"]["input"] for it in judge_iterations]
    judge_output_tokens = [it["judge_result"]["tokens"]["output"] for it in judge_iterations]

    result["summary"].update({
        "total_judge_input_tokens": sum(judge_input_tokens),
        "total_judge_output_tokens": sum(judge_output_tokens),
        "avg_judge_input_tokens": sum(judge_input_tokens) / len(judge_input_tokens),
        "avg_judge_output_tokens": sum(judge_output_tokens) / len(judge_output_tokens),
    })


def print_criteria_breakdown(criteria: list[dict[str, Any]]) -> None:
    """Print a table showing criteria evaluation results."""
    if not criteria:
        return

    console.print("\n[bold]📊 Criteria Breakdown:[/bold]")
    criteria_table = Table(show_header=True, header_style="bold magenta")
    criteria_table.add_column("Status", style="cyan", width=12)
    criteria_table.add_column("Notes", style="white")

    for criterion in criteria:
        if isinstance(criterion, dict):
            passed = criterion.get("passed", False)
            notes = criterion.get("notes", "No notes provided")
            status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            criteria_table.add_row(status, notes)

    console.print(criteria_table)


def print_formatted_output(output: str, output_type: str, title: str, border_style: str) -> None:
    """Print output with appropriate formatting based on type."""
    # Remove markdown code blocks if present
    if output.startswith("```") and output.endswith("```"):
        lines = output.strip().split("\n")
        output = "\n".join(lines[1:-1])

    output_type_lower = output_type.lower()

    if "json" in output_type_lower or "fsl" in output_type_lower:
        try:
            import json
            parsed = json.loads(output)
            formatted = json.dumps(parsed, indent=2)
            syntax = Syntax(formatted, "json", theme="monokai", line_numbers=False)
            console.print(Panel(syntax, title=title, border_style=border_style))
        except:
            console.print(Panel(output, title=title, border_style=border_style))
    elif "python" in output_type_lower:
        syntax = Syntax(output, "python", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=title, border_style=border_style))
    elif "javascript" in output_type_lower or "js" in output_type_lower:
        syntax = Syntax(output, "javascript", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=title, border_style=border_style))
    else:
        console.print(Panel(output, title=title, border_style=border_style))


def print_scenario_results(scenario_id: str, result: dict[str, Any]) -> None:
    """Print a table of results for a single scenario."""
    print()  # Add newline before scenario table
    table = Table(title=f"Scenario: {scenario_id}")

    table.add_column("Iteration", style="cyan")
    table.add_column("Score", style="magenta")
    table.add_column("Criteria", style="white")
    table.add_column("Latency", style="yellow")
    table.add_column("Gen Tokens", style="blue")
    table.add_column("Judge Tokens", style="blue")
    table.add_column("Cache", style="blue")
    table.add_column("Status", style="green")

    failing_iterations = []

    if "iterations" in result:
        for iteration in result["iterations"]:
            iteration_num = str(iteration.get("iteration", "?"))

            if "error" in iteration:
                table.add_row(
                    iteration_num,
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    f"[red]ERROR: {iteration['error']}[/red]"
                )
                continue

            # Score
            score = "-"
            criteria_str = "-"
            status = "[yellow]No Judge[/yellow]"
            judge_tokens_str = "-"
            if "judge_result" in iteration:
                score_val = iteration["judge_result"].get("score", 0)
                score = f"{score_val:.0f}%"

                # Pass/fail based on criteria, not score
                criteria = iteration["judge_result"].get("criteria", [])
                passed_count, total_count = count_criteria_passed(criteria)
                if passed_count == total_count and total_count > 0:
                    criteria_str = f"[green]{passed_count}/{total_count}[/green]"
                    status = "[green]✓[/green]"
                else:
                    criteria_str = f"[red]{passed_count}/{total_count}[/red]"
                    status = "[red]✗[/red]"
                    # Collect failing iterations for detailed output
                    failing_iterations.append(iteration)

                # Judge tokens
                judge_tokens_data = iteration["judge_result"].get("tokens", {})
                judge_input = judge_tokens_data.get('input', 0)
                judge_output = judge_tokens_data.get('output', 0)
                if judge_input > 0 or judge_output > 0:
                    judge_tokens_str = f"{judge_input}/{judge_output}"

            # Latency
            latency = f"{iteration.get('latency_ms', 0)}ms"

            # Generation tokens
            tokens_data = iteration.get("tokens", {})
            input_tokens = tokens_data.get('input', 0)
            output_tokens = tokens_data.get('output', 0)
            cache_creation = tokens_data.get('cache_creation', 0)
            cache_read = tokens_data.get('cache_read', 0)

            # Build token and cache strings
            gen_tokens = f"{input_tokens}/{output_tokens}"

            cache = "-"
            if cache_creation > 0:
                cache = f"[yellow]Write: {cache_creation}[/]"
            elif cache_read > 0:
                cache = f"[green]Read: {cache_read}[/]"

            table.add_row(iteration_num, score, criteria_str, latency, gen_tokens, judge_tokens_str, cache, status)

    console.print(table)

    # Print detailed results for all iterations
    print_detailed_results(scenario_id, result)

    print()  # Extra newline for spacing


def print_detailed_results(scenario_id: str, result: dict[str, Any]) -> None:
    """Print detailed results for a scenario (both passing and failing iterations)."""

    output_type = result.get("scenario_json", {}).get("output_type", "")

    # Determine if scenario passed or failed overall
    has_failures = False
    if "iterations" in result:
        for iteration in result["iterations"]:
            if "error" in iteration:
                has_failures = True
                break
            if "judge_result" in iteration:
                criteria = iteration["judge_result"].get("criteria", [])
                if not all_criteria_passed(criteria):
                    has_failures = True
                    break

    # Print header with overall status
    if has_failures:
        console.print(f"\n[bold red]🔍 DETAILS: {scenario_id}[/bold red]")
        # Show prompt for context on failures
        prompt = result.get("scenario_json", {}).get("prompt", "No prompt")
        console.print(Panel(prompt, title="[yellow]Task[/yellow]", border_style="yellow"))
    else:
        console.print(f"\n[bold green]✓ DETAILS: {scenario_id}[/bold green]")

    # Show details for all iterations
    if "iterations" in result:
        for iteration in result["iterations"]:
            if "error" in iteration:
                continue

            iteration_num = iteration.get("iteration", "?")
            judge_result = iteration.get("judge_result", {})
            score = judge_result.get("score", 0)

            # Determine if this iteration passed based on criteria
            criteria = judge_result.get("criteria", [])
            iteration_passed = all_criteria_passed(criteria)
            color = "green" if iteration_passed else "red"

            console.print(f"\n[bold]📋 Iteration {iteration_num} - Score: {score:.0f}%[/bold]")

            # Reasoning
            reasoning = judge_result.get("reasoning", "No reasoning provided")
            console.print(Panel(reasoning, title=f"[{color}]Judge Reasoning[/{color}]", border_style=color))

            # Criteria breakdown
            criteria = judge_result.get("criteria", [])
            print_criteria_breakdown(criteria)

            # Differences (only for failures)
            if not iteration_passed:
                differences = judge_result.get("differences", [])
                if differences:
                    console.print(f"\n[bold]🔍 Key Differences:[/bold]")
                    for i, diff in enumerate(differences, 1):
                        console.print(f"  [red]{i}.[/red] {diff}")

            # Actual output
            actual_output = iteration.get("actual_output", "No output")
            console.print(f"\n[bold]💻 Output (Iteration {iteration_num}):[/bold]")

            # Determine title based on output type
            output_type_lower = output_type.lower()
            if "fsl" in output_type_lower:
                title = f"[{color}]FSL Output[/{color}]"
            elif "json" in output_type_lower:
                title = f"[{color}]JSON Output[/{color}]"
            elif "python" in output_type_lower:
                title = f"[{color}]Python Output[/{color}]"
            elif "javascript" in output_type_lower or "js" in output_type_lower:
                title = f"[{color}]JavaScript Output[/{color}]"
            else:
                title = f"[{color}]Text Output[/{color}]"

            print_formatted_output(actual_output, output_type, title, color)
