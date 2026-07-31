# Frontier Computational-Chemistry and General-Agent Landscape

## Evidence policy

This review separates peer-reviewed articles, preprints, official product
documentation, open repositories, and replication data. It uses open-source
repositories as architecture references, not as permission to copy code or
instructions. Complete metadata, source revisions, licensing decisions, and
limitations are in the [evidence ledger](frontier-agent-evidence-ledger.json);
the scholarly subset is independently checked in the
[citation audit](frontier-agent-citation-audit.json).

## Computational-chemistry agents

| System | Evidence status | Benchmarkable contribution | ChemSmart boundary |
| --- | --- | --- | --- |
| [El Agente Q](https://doi.org/10.1016/j.matt.2025.102263) | Peer-reviewed Matter article; replication data available | Hierarchical computational-chemist, geometry, quantum-calculation, and file-I/O roles; expert ORCA context; recovery and trace export | Use as an architecture benchmark only. No verified official reusable source repository was found, and traceability does not replace independent validation. |
| [ChemGraph](https://doi.org/10.1038/s42004-025-01776-9) | Peer-reviewed Communications Chemistry article and public [repository](https://github.com/argonne-lcf/ChemGraph) | Planner → independent per-species computations → typed aggregation | Strongest direct evidence for conditional decomposition, but only for selected decomposable reaction-property tasks. |
| [ACRA](https://doi.org/10.1038/s42004-026-01993-w) | Peer-reviewed chemputation article and public [repository](https://github.com/croningp/acra) | Critique coupled to deterministic XDL parsing and constrained simulation | Adjacent wet-chemistry evidence. It supports critic-plus-validator design, not an LLM critic as quantum-chemistry authority. |
| [ChemCrow](https://doi.org/10.1038/s42256-024-00832-8) | Peer-reviewed Nature Machine Intelligence article and public repository | Chemistry tool augmentation | Demonstrates tool augmentation, not a provenance-complete calculation agent. |
| [DynaMate](https://doi.org/10.1039/D5ME00062A) | Peer-reviewed article and public repository | Modular scheduling over expert-defined MD tools | Useful organization reference; limited direct evidence for autonomous or multi-agent superiority. |
| [MDCrow](https://arxiv.org/abs/2502.09565) | Preprint and public repository | Broad molecular-dynamics tool surface | Reference only: no independent scientific verifier or formal provenance layer. |
| [QUASAR](https://arxiv.org/abs/2602.00185) | Preprint and public repository | Checkpoints, restart, long-job check-ins, and atomistic workflow lifecycle | Reference only pending license, execution, and independent-evaluation review. |
| [VirtualLab_CC](https://github.com/CCBG-Lab/VirtualLab_CC) | Journal/repository record | Calculation-stage gates, evidence logs, structured result records | Early architecture reference; no broad role-system ablation. |
| [AiiDA](https://doi.org/10.1038/s41597-020-00638-4) and [QCSchema](https://github.com/MolSSI/QCSchema) | Peer-reviewed provenance infrastructure and open specification | Immutable process/data lineage and structured quantum-chemistry records | Use as a provenance and compatibility target, not as a required dependency. |

### What El Agente Q establishes—and does not establish

El Agente Q reports a role hierarchy, curated domain documents, tool-mediated
ORCA work, recovery from some actual errors, and executable trace export
([Zou et al., 2025](https://doi.org/10.1016/j.matt.2025.102263)). Its useful
lesson is that practical chemistry-agent behavior can arise from scoped tools,
expert constraints, and data-bearing artifacts rather than chemistry-specific
model fine-tuning.

It also exposes the boundary ChemSmart must address: hierarchy can lose
information, produce arbitrary approximations, choose an easier calculation,
or rationalize an unsupported result. ChemSmart therefore adopts typed
scientific state and independent validators rather than importing a large
fixed roster of roles.

### Evidence for conditional decomposition

ChemGraph is the most directly relevant published ablation. Its reported
planner–per-species–aggregation pattern improved reaction-enthalpy success for
GPT-4o-mini from 40% to 87% and for Claude 3.5 Haiku from 67% to 87%; its
reported Gibbs-energy results were 49% to 87% and 69% to 93%, respectively,
averaged across three runs ([Pham et al., 2026](https://doi.org/10.1038/s42004-025-01776-9)).

The implementable conclusion is narrow: delegate only when input partitioning
is scientifically real, outputs have a typed merge operation, and a
deterministic aggregator can check stoichiometry, units, and artifact identity.
It is not evidence that more agents always help.

### Evidence for critique and reproducibility

ACRA reports that adding critique to deterministic syntax and hardware-simulation
checks improved action/detail F1 in its chemputation setting
([Pagel et al., 2026](https://doi.org/10.1038/s42004-026-01993-w)). It motivates
a read-only critic that challenges missing evidence and assumptions, but it
does not validate an LLM's physical judgement. ChemSmart will require
deterministic checks such as electronic state, convergence, frequencies,
stoichiometry, units, and method compatibility before a critic can support a
scientific claim.

Reproducible documentation is a scientific infrastructure requirement rather
than a proven model-performance booster. AiiDA demonstrates durable
process/data provenance ([Huber et al., 2020](https://doi.org/10.1038/s41597-020-00638-4));
Workflow Run RO-Crate demonstrates a workflow-provenance packaging model
([Leo et al., 2024](https://doi.org/10.1371/journal.pone.0309210)). ChemSmart
will use these as design references for evidence bundles and derived reports.

## Frontier general-agent harnesses

| System | Publicly documented harness capabilities | Training-evidence boundary | ChemSmart implication |
| --- | --- | --- | --- |
| [Codex](https://github.com/openai/codex) | Iterative model/tool loop, durable thread state, approvals, sandboxing, worktrees, skills, and an app-server protocol | Earlier Codex research documents real-repository RL; a full recipe for current frontier models is not public | Preserve typed tool outcomes, isolated workspaces, approvals, and test-derived evidence. |
| [Claude Code](https://code.claude.com/docs/en/sub-agents) | Hierarchical instructions, isolated subagents, hooks, permissions, sandboxing, MCP, and progressive skills | Product documentation does not establish that a current Claude model was trained on the exact product harness | Keep policy in deterministic hooks/validators; give specialists narrow, fresh task packets. |
| [Kimi Code](https://github.com/MoonshotAI/kimi-code) and [K2/K2.5/K3](https://arxiv.org/abs/2607.24653) | Goals, JSONL sessions, approvals, resumable/nested workers, skills, and cross-harness experimentation | K2/K2.5/K3 are technical reports rather than independent peer review | Build a provider-portable harness and distinguish opaque continuation state from scientific evidence. |

The central consequence is that ChemSmart should not imitate a single vendor
surface. K3's reported cross-harness training argues against assuming that a
frontier model has one uniquely native scaffold. The practical common core is a
typed tool loop, progressive task-local instructions, durable state, explicit
approval, isolation, and outcome-based verification.

## Open-source skill and repository policy

| Candidate | Decision | Reason |
| --- | --- | --- |
| OpenAI `cli-creator` at `49f948f…` | Concept reference only | The inspected repository metadata reports no asserted license. No text or code is copied. |
| K-Dense `scientific-writing`, `scientific-critical-thinking`, and `peer-review` at `ab2f84a…` | Clean-room concept reference | MIT source; useful claim, falsification, and review concepts, but the broad collection is not installed. |
| AtomisticSkills units/FAIR-data references at `e4a1ba1…` | Clean-room concept reference | MIT source; direct ORCA workflow execution could bypass ChemSmart approvals and receipts. |
| DPDispatcher `dpdisp-submit` at `92be874…` | Future adapter reference only | LGPL-3.0-or-later, shell/network/remote-execution surface, and incompatible secret/receipt assumptions require a separately approved adapter. |

## Decision for ChemSmart

1. Keep one provider-neutral, event-sourced core and provider-specific adapters.
2. Keep a single-agent reference path; add decomposition only behind a typed
   task graph and a preregistered benefit gate.
3. Treat documentation as evidence rendering over native and structured
   artifacts, not free-form post-hoc narration.
4. Treat critique as a bounded detector with independent arbitration, not a
   voting system or scientific authority.
5. Capture visible action/outcome traces now; defer SFT, preference training,
   and RL until held-out, reproducible evaluation exists.

The concrete architecture and staged gates are specified in
[chemsmart-agent-ultimate-goal.md](../design/chemsmart-agent-ultimate-goal.md).
