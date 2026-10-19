"""Actual Pi harness under Inspect's sandbox agent bridge."""

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.agent import Agent, AgentState, agent, sandbox_agent_bridge
from inspect_ai.dataset import Sample
from inspect_ai.model import user_prompt
from inspect_ai.scorer import Score, Target, accuracy, scorer
from inspect_ai.solver import TaskState
from inspect_ai.util import sandbox, store

ROOT = Path(__file__).resolve().parent
GLOBAL_PATH = "/home/agent/.pi/agent/AGENTS.md"
PROJECT_PATH = "/workspace/AGENTS.md"
GLOBAL_SENTINEL = "Global sentinel: keep all existing owner preferences."
PROJECT_SENTINEL = "Project sentinel: this is a fictional staging workspace."


@agent
def pi_instruction_agent() -> Agent:
    async def execute(state: AgentState) -> AgentState:
        await sandbox().write_file(GLOBAL_PATH, GLOBAL_SENTINEL + "\n")
        await sandbox().write_file(PROJECT_PATH, PROJECT_SENTINEL + "\n")
        async with sandbox_agent_bridge(state) as bridge:
            model_config = {
                "providers": {
                    "inspect-bridge": {
                        "baseUrl": f"http://127.0.0.1:{bridge.port}/v1",
                        "api": "openai-completions",
                        "apiKey": "bridge-test-only",
                        "models": [{
                            "id": "bridge-model",
                            "name": "Inspect bridge model",
                            "reasoning": False,
                            "input": ["text"],
                            "contextWindow": 131072,
                            "maxTokens": 2048,
                            "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                        }],
                    }
                }
            }
            await sandbox().write_file(
                "/home/agent/.pi/agent/models.json", json.dumps(model_config)
            )
            prompt = user_prompt(state.messages).text
            result = await sandbox().exec(
                ["pi", "--mode", "json", "--no-session", "--offline", "--no-mcp",
                 "--provider", "inspect-bridge", "--model", "bridge-model", prompt],
                env={"PI_CODING_AGENT_DIR": "/home/agent/.pi/agent", "PI_OFFLINE": "1"},
                timeout=180,
            )
            if not result.success:
                raise RuntimeError(f"Pi failed; stderr tail: {result.stderr[-300:]}")
            events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
            started = [event.get("toolName") for event in events if event.get("type") == "tool_execution_start"]
            errors = sum(bool(event.get("isError")) for event in events if event.get("type") == "tool_execution_end")
            store().set("pi_tool_calls", len(started))
            store().set("pi_tool_errors", errors)
            store().set("pi_tool_names", sorted(set(started)))
            return bridge.state
    return execute


def scope_objective_checks(global_text: str, project_text: str) -> dict[str, bool]:
    """Only inspect observable placement; semantic rule quality needs a reviewer."""
    global_rest = global_text.replace(GLOBAL_SENTINEL, "", 1).strip()
    project_rest = project_text.replace(PROJECT_SENTINEL, "", 1).strip()
    return {
        "objective_preserved_global": GLOBAL_SENTINEL in global_text,
        "objective_preserved_project": PROJECT_SENTINEL in project_text,
        "objective_scoped_placement": bool(global_rest and project_rest),
    }


@scorer(metrics=[accuracy()])
def instruction_scope_state() -> object:
    async def score(state: TaskState, target: Target) -> Score:
        global_text = await sandbox().read_file(GLOBAL_PATH)
        project_text = await sandbox().read_file(PROJECT_PATH)
        checks = scope_objective_checks(global_text, project_text)
        objective_passed = all(checks.values())
        return Score(
            value=0,
            metadata={
                **checks,
                "objective_checks_passed": objective_passed,
                "semantic_review_required": objective_passed,
                "semantic_review_status": "pending" if objective_passed else "not_applicable",
                "semantic_review_reason": (
                    "Review full brittle-workaround rule, prompt risk explanation, research before "
                    "extension, negation, and project-only catalog permission scope."
                    if objective_passed else None
                ),
                "harness_tool_calls": store().get("pi_tool_calls", 0),
                "harness_tool_errors": store().get("pi_tool_errors", 0),
                "harness_tool_names": store().get("pi_tool_names", []),
            },
            explanation=(
                "Objective file checks passed; semantic instruction quality requires rubric review."
                if objective_passed else "Disposable instruction files failed objective placement or preservation checks."
            ),
        )
    return score


@task
def pi_scope() -> Task:
    row = next(
        row for row in json.loads((ROOT / "tasks/agent-instructions.json").read_text())
        if row["id"] == "instruction_scope_ambiguous_reference"
    )
    return Task(
        dataset=[Sample(
            id=row["id"], input=row["prompt"], target="Correctly scoped instruction edits",
            metadata={"category": row["category"], "fixture": "tasks/agent-instructions.json", "harness": "pi@1.1.0"},
        )],
        solver=pi_instruction_agent(),
        scorer=instruction_scope_state(),
        sandbox=("docker", str(ROOT / "inspect/pi/compose.yaml")),
        time_limit=200,
        display_name="Mattbench agent instructions: Pi in disposable sandbox",
        version="2",
    )
