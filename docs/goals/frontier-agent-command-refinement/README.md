# Command-Compiled Frontier Agent Roadmap — Historical

> This M0–M6 roadmap is preserved as the command-compiler lineage but is
> superseded for new sessions by the
> [Two-Frontier Paper Research roadmap](../two-frontier-paper-research/README.md).
> Do not copy its goal commands as the active project goal. In particular, its
> earlier provider-thinking instruction is historical.

## Purpose and status

This directory is the operational roadmap for a ChemSmart CLI-first frontier
agent. It changes the working objective from prompt-written engine inputs to
semantic command compilation:

~~~text
research goal -> ScientificTaskSpec -> CommandWorkflowSpec
-> canonical ChemSmart command -> safe CLI preview -> approval
-> execution -> validation -> evidence report
~~~

This is an implementation plan, not a claim that an engine was run, a result
was reproduced, or a system is SOTA. Until an explicit execution authorization
exists, a new workflow may become only planned or previewed. An archived
artifact may become validated only with a complete deterministic receipt.

## Non-negotiable command boundary

Models propose typed scientific and command-workflow data. They never write,
edit, or execute Gaussian, ORCA, or xTB native inputs; choose shell quoting or
option placement; pass arbitrary paths; or use a native-input fallback.
ChemSmart's deterministic compiler owns live Click-schema resolution, trusted
project/artifact grounding, canonical long-flag argv rendering, safe preview,
independent parser observation, intent round-trip comparison, and the
preflight receipt.

Use existing CLI commands as the compositional language. A multi-step chemistry
workflow is a dependency DAG of canonical ChemSmart commands, not a plan to
manufacture engine input files. A later node consumes only a real prior
artifact receipt and hash; without one it remains planned.

## Working persona

Work as a computational-chemistry expert during experimental development.
Uphold scientific integrity, make facts and uncertainty explicit, treat
failure as evidence for a better design, and collaborate with bounded
research/domain-advisor agents through typed inputs and deterministic merges.
The long-term aspiration is a rigorous state-of-the-art paper, but no phase
may use that aspiration to overstate results or bypass validation.

## Authority, APIs, and test cadence

Read AGENTS.md first. DeepSeek is the only model provider for actual harness
experiments. Elsevier, SerpAPI, and Tavily are limited to literature discovery
and source verification. Borrow credentials only through a standard Keychain
lease, validate liveness and current-quota sufficiency without recording a
secret, and never top up or alter billing. Treat an Elsevier 403 as an
entitlement state until evidence proves otherwise.

During a phase, use inspection and deterministic receipts rather than repeated
pytest, Ruff, or broad checks. Run one focused suite after a material milestone
and at most one evidence-driven rerun. Run the full agent/lint/schema/link/
citation/secret/diff gate only after M5 freezes the harness and protocol.

## Phase sequence

| Phase | Focus | Gate document |
| --- | --- | --- |
| M0 | provenance, command-first control, local skills, phase goals | [M0](M0-authority-and-command-control.md) |
| M1 | frozen baseline and constrained DeepSeek command proposal | [M1](M1-command-baseline-and-provider-validation.md) |
| M2 | canonical IR, compiler, semantic-preflight ablation | [M2](M2-command-workflow-compiler.md) |
| M3 | approval consumption and invocation provenance | [M3](M3-approval-and-command-provenance.md) |
| M4 | command DAG and archived scientific evidence slice | [M4](M4-command-dag-and-archived-slice.md) |
| M5 | pilot, preregistration, and integration freeze | [M5](M5-pilot-and-preregistration.md) |
| M6 | externally custodied confirmatory study and paper draft | [M6](M6-confirmatory-study-and-paper.md) |

The [goal commands](goal-commands/README.md) are copyable new-session prompts.
They are deliberately bounded; select only the next incomplete phase and do
not silently advance through a gate.

## Evidence-driven refinement

Refine the harness when a source inspection, safe-preview trace, held-out
fixture, verified literature record, or independent critique identifies a
specific defect or opportunity. Record the observation, hypothesis, change,
deterministic result, and remaining limitation. Keep a single-agent reference
path. Optional subagents, evidence composition, and read-only critics remain
experimental until the preregistered gates support adoption.

The bounded design evidence for command compilation, repair, property/
differential testing, and limited decomposition is in
[command-compiled-design-evidence.md](../../research/command-compiled-design-evidence.md).
The active typed contract and intentionally narrow M2 support boundary are in
[command-workflow-spec-v1.md](../../design/command-workflow-spec-v1.md).
