---
paths:
  - "chemsmart/**"
  - "tests/**"
  - "scripts/**"
---

# Project Conventions (legacy code supplement)

`AGENTS.md` is authoritative for mission, approvals, evidence, and scope.
These conventions remain useful when touching code, but dated architecture
claims must be checked against the current source and tests.

For the command-compiled frontier milestones, do not run pytest, Ruff, or
broad checks after each edit. Use inspection and deterministic receipts during
implementation, then run one focused suite after a material milestone and the
preregistered full gate only after the freeze milestone.

## Identity & scope

chemsmart: open-source computational chemistry planning & HPC automation
toolkit (Python 3.10+). Gaussian/ORCA job generation, submission, analysis,
plus the agent/TUI layer (`chemsmart/agent/`). Local model path (MLX 4-bit,
Apple Silicon) and cloud providers (OpenAI-compatible/Anthropic) both exist.

## Python style

- Python 3.10 target, type hints on params/returns, PEP 8, line length 79.
- f-strings; context managers for resources; docstrings on public API;
  composition over inheritance.
- Format `black` (79) + `isort` (profile=black); lint `ruff`/`flake8`.
- Never print install commands (`pip/brew/apt install`) in code or docs.

## Testing

- `pytest --strict-markers --disable-warnings`; agent tests in
  `tests/agent/`; markers: `slow`, `agent`, `integration`.
- Every behavior change ships with a test. For M0–M4, run the focused suite
  once only after the material milestone is complete, with at most one
  evidence-driven rerun. Reserve the full `tests/agent/` suite for the M5
  freeze gate.
- Some legacy LLM execution surfaces and their tests have historical
  compatibility constraints. Inspect the active runtime and focused tests
  before changing them; do not infer that a live execution interface is
  deprecated merely from this document.

## Architecture map (agent layer)

- CLI entry: `chemsmart.cli.main:main` (Click).
- Unified agent loop: `chemsmart/agent/core.py` (AgentSession.run_loop) +
  `loop.py` (ToolLoop) + `registry.py` (ToolRegistry, TOOL_GROUPS).
- Command synthesis: `chemsmart/agent/synthesis.py` (SynthesisSession;
  captures `_last_reasoning`); schema pruning `schema_prune.py`.
- Command tools: `command_workflow_tools.py` is the active typed frontier
  surface; `tools_command.py` is legacy host/baseline compatibility only.
- Training capture: `training_log.py` writes append-only turn snapshots to
  `var/agent-training/` and model-specific `runs/<model>/` stores. The
  exporter reconstructs positive/review session chains and separate repair
  contrasts; the auditor reports terminal-gate, multi-turn-session,
  diversity, and canonical-kind coverage metrics. Implementations are
  `scripts/training/export_sft.py` and
  `scripts/training/audit_dataset.py`.
- System prompt assembly: `prompts/identity.py:build_system_prompt`.
- Workspace project YAML: `./.chemsmart/<program>/<name>.yaml`
  (`chemsmart/settings/workspace_project.py`).

## Key dependencies (pinned facts)

`numpy~=1.26.4` (numpy-2 ABI is a known trap), `pydantic>=2`, `click`,
`transformers==4.56.2` (local path), `textual` (TUI). Dev: `black`,
`isort`, `ruff`, `pre-commit`.
