# Two-Frontier Agent Landscape

## Evidence method

This review records `observable mechanism -> evidence class -> benchmark
artifact -> adopted rule -> rejected inference`. Peer-reviewed papers,
preprints, vendor documentation, public code, and replication data are not
treated as interchangeable. The nine entries in the project BibTeX were
rechecked on 2026-08-01 through Crossref or arXiv. The
[machine-readable ledger](frontier-agent-evidence-ledger.json) records wider
discovery metadata, but only repositories with an explicit revision and
license field are reusable architecture candidates; unpinned repositories are
reference-only until separately audited. See the
[citation audit](frontier-agent-citation-audit.json) for its exact scope.

## Frontier computational-chemistry agents

| System | Evidence and benchmark artifact | Observable mechanism | Adopted rule | Rejected inference |
| --- | --- | --- | --- | --- |
| [El Agente Q](https://doi.org/10.1016/j.matt.2025.102263) | Peer-reviewed Matter article; [replication-data record](https://doi.org/10.5683/SP3/JU2BQK), whose license is not yet verified | The article reports a hierarchical agent, human-authored procedures/context, ORCA-centered tool use, adaptive troubleshooting, and exported action traces | Use the paper to define behavior/rubric dimensions; keep ingestion or reuse of the released data blocked until its license permits the intended benchmark use | No verified official reusable implementation repository exists. Do not reuse the unrelated Agent-Q repository or infer that model-authored ORCA input is safe. |
| [El Agente Quntur](https://arxiv.org/abs/2602.04850) | Preprint v2; [dataset](https://doi.org/10.5683/SP3/RDSOEA), CC BY-NC-ND 4.0 | Hierarchical research collaborator, literature/manual deep research, general composable ORCA actions, 17 benchmark exercises | Use unchanged, private data only as a broad knowledge/research reference where license permits | Not peer reviewed; no verified official reusable implementation repository; no adaptation or redistribution of the dataset. |
| [ChemGraph](https://doi.org/10.1038/s42004-025-01776-9) | Peer-reviewed article, Apache-2.0 [repository](https://github.com/argonne-lcf/ChemGraph/tree/e00472d4822310cb44e03c0a9edeeb2f587d7c3b), [Zenodo evaluation archive](https://zenodo.org/records/17290519) | LangGraph/ReAct tools, serialized molecular objects; planner -> independent species workers -> deterministic reaction-property aggregation | Permit decomposition only for scientifically independent branches with typed stoichiometric/unit/hash joins | Reported gains on selected enthalpy/Gibbs tasks do not establish a permanent large hierarchy or universal multi-agent superiority. |
| [ACRA](https://doi.org/10.1038/s42004-026-01993-w) | Peer-reviewed adjacent chemputation work and public repository | Critique paired with deterministic XDL parsing and constrained execution checks | Use a read-only critic as a defect detector alongside deterministic validation | Wet-chemistry workflow evidence is not quantum-chemistry authority; critic opinion alone cannot establish physical validity. |
| [ChemCrow](https://doi.org/10.1038/s42256-024-00832-8) | Peer-reviewed article and public repository | Chemistry tool augmentation and task-oriented tool selection | Retain tool-surface design as a secondary reference | Chemistry-tool breadth does not establish quantum-workflow fidelity or provenance completeness. |
| [DynaMate](https://doi.org/10.1039/D5ME00062A) | Peer-reviewed article and public repository | Modular scheduling over expert-defined simulation components | Retain modular workflow composition as a secondary reference | The paper does not establish universal autonomous or multi-agent superiority. |
| [MDCrow](https://arxiv.org/abs/2502.09565) | Preprint and public repository | Expert-defined molecular-dynamics tool catalog | Retain domain-tool scoping as a secondary preprint reference | It is not peer reviewed and does not supply ChemSmart's provenance or quantum-chemistry validator. |
| [QUASAR](https://arxiv.org/abs/2602.00185) | Preprint and public repository | Reported checkpoint, restart, and long-job check-in mechanisms | Retain recovery mechanisms as hypotheses for bounded evaluation | Author-designed preprint evidence does not establish a safe ChemSmart execution policy. |
| [VirtualLab_CC](https://doi.org/10.1016/j.aichem.2026.100129) | Journal article, public repository, and Zenodo record | Calculation-stage gates, structured result records, and evidence logs | Retain lifecycle/evidence organization as a secondary reference | A young work-in-progress repository with limited published ablation cannot establish frontier efficacy. |
| [AiiDA](https://doi.org/10.1038/s41597-020-00638-4), [QCSchema](https://github.com/MolSSI/QCSchema), [Workflow Run RO-Crate](https://doi.org/10.1371/journal.pone.0309210) | Peer-reviewed provenance infrastructure and open specification | Typed records, immutable process/data lineage, workflow-run packaging | Use as structured-record and manifest compatibility references | Provenance formats do not themselves validate chemistry. |

### Direct benchmark policy

El Agente Q is a prospective behavior-and-artifact benchmark, not a code
benchmark. Its paper can define interpretation and workflow-completeness
dimensions. The released archive must not be ingested, adapted, or
redistributed until its license and the intended benchmark use are verified.
If admitted, ChemSmart replaces model-authored native input with:

```text
source-located ProtocolClaim
  -> MolecularSystemSpec and ProjectConfigSpec
  -> validated project YAML
  -> CommandWorkflowSpec
  -> live-schema compiler and safe preview
```

ChemGraph is the direct decomposition benchmark. Its paper evaluates a
multi-agent variant on `react2enthalpy` and `react2gibbs`; this is direct but
narrow evidence for decomposing independently computable species and then
applying a deterministic aggregation. The ChemSmart experiment must preserve
that eligibility condition and keep a single-agent comparator.

Computational knowledge is externalized in versioned `DomainKnowledgePack`
records with engine/version scope, literature provenance, rule IDs, allowed
settings, prohibitions, and deterministic validators. A fluent persona is not
a knowledge source.

## Frontier general-agent harnesses

| Harness | Public mechanism and code | Training known | Training unknown | ChemSmart adoption |
| --- | --- | --- | --- | --- |
| [Codex loop](https://openai.com/index/unrolling-the-codex-agent-loop/), [harness](https://openai.com/index/unlocking-the-codex-harness/), [source](https://github.com/openai/codex/tree/ee0247f95a6fe2b094ba2253d82cae2a2b4c2dff) | Official engineering posts describe one shared loop, exact-prefix history growth, approval/sandbox boundaries, and an App Server around the harness; Apache-2.0 source is inspectable | Named-model vendor announcements make high-level coding-RL/co-tuning claims; the cited harness posts themselves describe engineering, not a training recipe | Exact current corpus, rewards, and proof that every API model uses the pinned open harness | `HC`: add public event-prefix replay to the common sandbox, approval, and validator baseline |
| [Claude Code](https://code.claude.com/docs/en/how-claude-code-works), [subagents](https://code.claude.com/docs/en/sub-agents), [long-running harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Gather-act-verify, session state, compaction, progressive skills, fresh restricted subagents, hooks, and a fresh-context progress-artifact experiment | The cited sources document product behavior and harness experiments; they do not disclose a harness-specific post-training procedure | No public exact Claude-Code-schema RL recipe; core product harness is not a complete open-source implementation | `HA`: progressive skills, fresh typed specialists, deterministic hooks, structured progress handoff |
| [Kimi Code](https://github.com/MoonshotAI/kimi-code/tree/e22479a62eed9c3b78a67b313f4332c2c0ba9670), [Kimi K3](https://arxiv.org/abs/2607.24653), [report source](https://github.com/MoonshotAI/Kimi-K3/tree/7c5be9599120d7993748de66a76128614f15f210) | The pinned MIT harness exposes goals, approvals, sessions, forks, compaction, and nested-agent patterns; the K3 vendor preprint reports cross-harness evaluation/training mechanisms | The K3 report describes verified/human SFT data, specialist RL stages, budget-aware rewards, final-state verifiers, and hidden graders | Complete trajectories, RL environment/implementation, and independent replication; the report is not peer reviewed | `HK`: add persistent goals and checkpoint/fork/resume to the HA feature set, with depth-two bounded delegation |

OpenAI explicitly notes that cross-provider protocols can lose provider-specific
tool/session semantics when reduced to a common subset. ChemSmart therefore
uses a provider-neutral scientific kernel but preserves rich native envelopes.
`ProviderStateRef` is opaque and non-evidentiary; it must never be flattened
into a scientific rationale.

### Provider-documentation boundary

Official DeepSeek documentation currently lists `deepseek-v4-flash`, documents
the `reasoning_content` continuation required for thinking-mode tool calls, and
declares a 1M-token context window on its model/pricing page. These are vendor
interface declarations, not observations that ChemSmart preserved one million
tokens, that thinking-disabled mode works, or that thinking improves outcomes.
The relevant records are the [model list](https://api-docs.deepseek.com/api/list-models),
[thinking guide](https://api-docs.deepseek.com/guides/thinking_mode/), and
[model/pricing page](https://api-docs.deepseek.com/quick_start/pricing/).

Elsevier documents article retrieval at
`https://api.elsevier.com/content/article/doi/{doi}` and separately documents
article-access entitlement. Therefore a successful metadata probe does not
establish full-text entitlement, and an access denial must be classified before
being called an invalid key. See the official
[Article Retrieval API](https://dev.elsevier.com/documentation/ArticleRetrievalAPI.wadl)
and [article-access guidance](https://dev.elsevier.com/tecdoc_article_access.html).

## Training synthesis

Within this dated and deliberately small source set, the K3 vendor report
contains the most detailed training description. That is a comparative review
judgment, not independent validation or a claim of reproducibility. The
transferable hypotheses are:

1. construct tasks as initial state, constrained goal, typed action space,
   budget, and independent final-state verifier;
2. create SFT cold starts from verified accepted and rejected visible traces;
3. train across multiple harness configurations to reduce scaffold overfit;
4. use public diagnostic graders plus held-out hidden graders and bounded
   submissions to reduce reward hacking;
5. reward artifacts and receipts, never the model's self-reported success.

ChemSmart defers training until paper-level gold tasks and deterministic
chemistry graders exist. Hidden reasoning, provider state, secrets, and raw
licensed full text are excluded from training traces.

## Architecture decision

Implement one kernel plus four cumulative experimental profiles. Sandboxed
tools, approval pause, and deterministic validator feedback are active in all
four and are not experimental toggles.

| Profile | Public event replay | Progressive skills, fresh specialists, hooks, handoff, compaction | Persistent goal and checkpoint/fork/resume | Maximum delegation depth |
| --- | --- | --- | --- | ---: |
| `H0` | no | no | no | 0 |
| `HC` | yes | no | no | 0 |
| `HA` | yes | yes | no | 1 |
| `HK` | yes | yes | yes | 2 |

Run the same DeepSeek V4 Flash tasks, tools, schema, budget, and order through
all profiles. Select the smallest safe non-inferior profile from tool-call
validity, scientific fact preservation, false completion, repair, context
loss, cost, and latency. This is an empirical provider-conformance decision,
not a claim that DeepSeek was trained on any one of these product harnesses.

The literature and repository evidence justifies testing these mechanisms; it
does not make a profile effective by citation. Only the preregistered crossover
and paper-level gates can support adoption.
