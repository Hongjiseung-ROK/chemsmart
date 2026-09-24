# R10 episode Q13 -- what the programs print that the Agent never sees

Base SHA: 4db49c22b6dfab29a4ceca9eba4b59245bda0b7e (verified with `git rev-parse HEAD` at start).
Researcher model: claude-opus-5-5[1m]. Agent under study: deepseek-v4-flash-0731 (alibaba-token-plan).

## The question (as currently understood)

Which quantities Gaussian, ORCA, PySCF and xTB print that bear on the science
the Agent is asked to do reach it as neither typed evidence nor a pointer to
where they sit? For each one that matters: can the hub serve it under the same
reader contract as every other selector, or, failing that, can the Agent be
told truthfully that the output holds it? Does serving it change what the
Agent concludes?

Two failure shapes are hunted:
- a printed quantity the science needs that no reader serves;
- a host statement of absence ("not determined") about something the output
  determines.

## Falsifier of the premise (from the brief)

Census the archived real outputs under /project/xlzhang/jiseung/ (sealed goals
r10/q6/goals and r10/q3 excluded; the master's r10/m* excluded) and tests/data.
If the quantities that matter are only the few named in the brief (PySCF
real->complex stability and the stability eigenvalues, Gaussian <R**2> and
molar volume, ORCA Hirshfeld spin populations), serve those and end. If a live
goal shows serving them changes nothing the Agent concludes, that is the
result.

## Status

- Census: in progress.
