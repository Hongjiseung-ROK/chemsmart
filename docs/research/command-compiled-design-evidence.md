# Command-Compiled Agent Design: Evidence Addendum

## Scope

This addendum supports a narrow design choice: ChemSmart should compile typed
scientific intent into canonical CLI invocations instead of letting a model
write Gaussian, ORCA, or xTB native inputs. It is not an empirical result about
ChemSmart, an execution result, or evidence that any component improves
scientific reasoning.

The companion [source ledger](command-compiled-design-evidence-ledger.json)
and [citation audit](command-compiled-design-citation-audit.json) record
retrieval provenance. The bibliography is
[command-compiled-design-references.bib](command-compiled-design-references.bib).
The [open-source skill adoption ledger](open-source-skill-adoption-ledger.json)
records exact revisions, reviewed files, executable/dependency surface, and
clean-room decisions. All external repositories are reference-only; no
upstream implementation is vendored or executed by this roadmap.

## Design evidence and bounded inferences

| Source | What it supports | What it does not support |
| --- | --- | --- |
| `ccmd-001` · [NL2Bash](https://aclanthology.org/L18-1491/) | Treat natural-language-to-command generation as semantic parsing with an observable execution language. | Shell strings from a model are safe, chemically correct, or suitable as ChemSmart's runtime authority. |
| `ccmd-002` · [PICARD](https://aclanthology.org/2021.emnlp-main.779/) | Constraining generation against a formal parser can prevent invalid partial structures. | Direct token-level constrained decoding is available through DeepSeek or guarantees semantic/scientific correctness. ChemSmart therefore uses typed tool-call IR and deterministic compilation instead. |
| `ccmd-003` · [Synthesize, Execute and Debug](https://proceedings.neurips.cc/paper_files/paper/2020/hash/cd0f74b5955dc87fd0605745c4b49ee8-Abstract.html) | Execution observations can drive bounded, structured repair. | A model may freely regenerate commands after a failure. ChemSmart returns a minimal counterexample and permits at most two constrained repairs. |
| `ccmd-004` · [QuickCheck](https://doi.org/10.1145/357766.351266) and [Hypothesis](https://doi.org/10.21105/joss.01891) | Property-based tests can generate equivalence and invariant cases beyond manually enumerated examples. | Generated tests provide a chemical oracle or replace independent validation. |
| `ccmd-005` · [Csmith](https://github.com/csmith-project/csmith) | Differential-testing design can expose disagreement between independent implementations. | Randomly generated chemistry or commands establish a valid scientific result. |
| `ccmd-006` · [ChemGraph](https://doi.org/10.1038/s42004-025-01776-9) | Independently computable chemistry components can justify limited decomposition and deterministic aggregation. | A permanent large specialist hierarchy or broad multi-agent superiority. See the existing ChemGraph record in [the frontier ledger](frontier-agent-evidence-ledger.json). |

## Implementation consequences

1. The model proposes ScientificTaskSpec and CommandWorkflowSpec JSON only.
   It does not choose shell syntax, paths, flag aliases/order, or native-engine
   input text.
2. The compiler is the sole command authority. It checks the DAG, resolves the
   live Click schema and trusted project/artifact bindings, renders canonical
   long flags, runs a safe CLI preview, obtains an independent parser
   observation, and compares semantic intent.
3. Property tests cover invariants such as canonicalization of legal aliases
   and option order, preservation under paraphrase, rejection of injection and
   stale bindings, and detection of program-kind/constraint drift.
4. Differential tests compare compiler output with an independent parser and
   generated-input semantic parser. A disagreement is a defect or block, not a
   tie resolved by a model.
5. Repair is counterexample-guided and bounded. It cannot alter an explicit
   program, geometry, charge, multiplicity, method, or constraint without a
   new scientific specification and approval decision.
6. Task decomposition remains conditional. Use it only for typed independent
   nodes with immutable inputs, explicit budgets, one mutable owner per
   artifact/project, and deterministic joins.

## Evaluation consequence

Before the 2 x 2 x 2 decomposition/evidence/critic study, preregister a paired
front-end comparison: A0 direct command string versus A1 typed IR plus
deterministic compiler. Require deterministic rendering and parser acceptance,
no shell injection/hallucinated options/native-input authoring, preserved
explicit intent, and the thresholds in the ablation protocol. This makes the
compiler a safety boundary immediately while reserving efficacy claims for
measured evidence.
