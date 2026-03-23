# Skill Evaluations

Shared evaluation framework for testing agent skills using LLM-as-judge methodology.

## Setup

1. **Install dependencies:**

   ```bash
   cd evals
   uv sync
   ```

2. **Set API key:**
   ```bash
   # Option 1: Export directly
   export ANTHROPIC_API_KEY=your-key-here

   # Option 2: Create .env file and source it
   echo 'ANTHROPIC_API_KEY=your-key-here' > .env
   source .env
   ```

## Usage

```bash
# Run all scenarios for all skills
uv run run_evals.py

# Run all scenarios for a specific skill
uv run run_evals.py --skill felt-map-maker

# Run a specific scenario
uv run run_evals.py --skill felt-map-maker --scenario simple-point

# Use different models
uv run run_evals.py --model claude-sonnet-4-5-20250929 --judge-model claude-opus-4-5-20251101
```

## Creating New Scenarios

Scenarios live inside each skill's directory at `skills/<skill-name>/scenarios/`.

Use an existing scenario as a template:

```bash
# Copy from an existing scenario
cp -r skills/felt-map-maker/scenarios/simple-point skills/felt-map-maker/scenarios/your-new-scenario

# Edit the files (see structure below)

# Test locally
uv run run_evals.py --skill felt-map-maker --scenario your-new-scenario
```

### Scenario Structure

Each scenario directory contains:

#### Scenario configuration `scenario.json`

```json
{
  "prompt": "Detailed instructions for the AI to follow",
  "output_type": "FSL",
  "criteria": [
    "Check that version is '2.3.1'",
    "Must include required properties..."
  ]
}
```

**Fields:**
- `prompt` - Instructions given to the model
- `output_type` - Output format: `"FSL"`, `"PYTHON"`, or `"TEXT"`
- `criteria` - Evaluation criteria for the judge

#### Reference implementation `reference.*`

Expected "correct" output that the judge compares against:
- `reference.json` for FSL
- `reference.py` for Python
- `reference.txt` for text

#### Layer data `data.csv` (optional)

Sample layer attributes the AI can reference for styling.

## Output

Results are saved to `results/`:

```
results/
└── 2026-01-20_10-30-00/
    ├── summary.json
    ├── felt-map-maker/
    │   ├── scenario-name/
    │   │   ├── iteration_1/
    │   │   │   ├── output.json
    │   │   │   └── evaluation.json
    │   │   └── summary.json
    │   └── ...
    └── ...
```
