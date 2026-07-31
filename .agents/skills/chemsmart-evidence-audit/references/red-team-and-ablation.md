# Red-team and ablation reference

Use a preregistered factorial study before enabling optional agent components.
Hold model/provider revision, prompt, tool schema, tasks, budgets, and order
policy fixed. Use held-out chemistry families and repeated paired runs.

## Components

- task decomposition: off/on;
- structured evidence/report generation: off/on;
- independent read-only critique: off/on.

Measure task success, chemical validity, clean-environment reproducibility,
false-pass and unsupported-claim rate, approval violations, critic precision
and recall, tool/parser errors, time, token use, cost, and handoff loss.

Adopt a component only when its preregistered benefit is supported without a
safety regression. Required red lines are zero approval bypasses, fabricated
evidence, artifact mutation, and successful completion with a required failed
deterministic gate.

Use deterministic graders first, expert rubrics second, and LLM judges only as
supplementary analysis.
