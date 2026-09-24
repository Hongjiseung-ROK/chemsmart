# R10 episode Q14 -- the refusals a hub should see coming

Base: `7450777c8d0e64dcf54773c736432d9f53c97ea7` (verified `git rev-parse HEAD`
at start). Model: claude-opus-5-5[1m]. Episode id `q14`.

## The question (as currently understood)

When the Agent asks for a calculation a program will certainly refuse or
waste, for a reason the hub can know from the request alone (method, basis,
job type, molecule, resources), does the hub translate it into the
equivalent calculation the program can run (visible in the review) or refuse
it at validation with a program-neutral route -- rather than spending an
approved engine call and a revision on it? And is a run the program finished
never given a failure word that says the engine failed?

## Falsifiers (armed before any repair)

- Premise falsified if, over the archived CUHK R8-R10 goals (sealed
  `r10/q6/goals/` and `r10/q3/` excluded) and the ax41 campaign workspaces,
  the failures predictable from the request are only the brief's instances,
  or are a small minority of failed engine calls. Then: fix those, report
  the rate as the result.
- A translation is wrong if the program's own number under the translated
  input differs from the untranslated physics (for a zero-pair system the
  correlated energy must equal the reference SCF energy to the printed
  precision; a numerical Hessian must reproduce analytic frequencies of the
  same method within the usual finite-difference noise, ~1 cm-1).
- A refusal is wrong if it fires on a request the program runs.

## Oracle

The program itself, run through `chemsmart run` in slot jobs: the refused
input and the translated input, side by side, on the same host (CUHK,
ORCA 6.1.1, PySCF 2.14.0).

## Status

- Census: in progress (provider-free, local copies of CUHK R8-R10 records
  and the ax41 mirror; host derivation `derive_run_outcome` on this tree).
- Jobs issued: none.
