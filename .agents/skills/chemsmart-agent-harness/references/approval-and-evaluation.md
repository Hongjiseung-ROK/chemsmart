# Approval and evaluation reference

## Approval matrix

| Operation | Default | Required evidence |
| --- | --- | --- |
| Read-only inspection or schema generation | allowed | command and artifact receipt |
| Fixture or fake execution | allowed within task scope | deterministic validation result |
| Real local calculation | explicit approval | exact command, inputs, environment, cost/resource bound |
| Scheduler submission, cancellation, or retry | explicit approval | exact job artifact, scheduler target, resource bound |
| Paid API, remote execution, or publication | explicit approval | provider/target, budget, disclosure scope |

Invalidate approval whenever a bound input, project, executable, environment,
or command hash changes.

## Bounded delegation

Dispatch only if subtasks have independent inputs and a typed merge operation.
The coordinator owns the task graph; workers own no shared mutable artifact.
Critics receive artifacts and declared assumptions, not persuasive self-reports.

## Evaluation rule

Keep a single-agent reference path. Compare it with any subagent or critic
configuration under fixed model, prompt, tool schema, task set, and budget.
Use deterministic outcome graders first. A component stays experimental until
it improves the preregistered metric without creating approval bypasses,
fabricated evidence, or false scientific passes.
