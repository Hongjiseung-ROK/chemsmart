# STATE (rendered by `generation.py close`; every fact is a ledger row)

Loop **g1** (parent g0). Ledger: 32 records, chain ok.

## Components adopted on evidence
- `generate` (tested, L0001,L0018,L0026): Candidates are enumerated, not recalled: every untested component falsifier, every claim's missing experiment, every unvalidated rule annotation and every observation of this generation is a source; the lead merges and words the slate and records what it dropped.
- `reflect` (tested, L0003,L0025): Every ledger row names the loop components responsible (attribution).
- `cascade` (promoted, L0004,L0014,L0020,L0021,L0022): L0 static, L1 archived replay, L2 provider-free, L3 planning-only live, L4 sealed goals.

## Decisions (newest last)
- L0024 no_promotion: M1 cannot promote a `next` policy under its own rule: 9 of 23 events resolved, 15 required
- L0027 promote: loop g0 -> g1: component `cascade` mutated
- L0028 promote: loop g0 -> g1: component `reflect` mutated
- L0029 promote: loop g0 -> g1: component `generate` mutated
- L0030 promote: loop g0 -> g1: component `state` mutated
- L0031 promote: loop g0 -> g1: component `next` mutated
- L0032 select: selected next action: payload_census -- Decompose the 27-61k-token first turn into prompt, tool 

## Open
- forecasts awaiting outcomes: 14 events (E02, E03, E04, E05, E06, E07 ...)
- loop components under most pressure: evaluators(6), generate(5), reflect(4), next(4)

## Slate (EIG bits / cost units / risk)
- * payload_census [agent_context] 0.9014 / 0.1 / 0
-   bypass_census [product] 0.3196 / 0.16 / 0
-   stream_replay_test [product] 0.147 / 0.12 / 1
-   defect_channel_ledger [product] 0.3785 / 0.48 / 0
-   seeded_flaw_replay [research_loop] 0.2546 / 0.6 / 0
-   R1a_planning_only [agent_context] 0.1742 / 3.6 / 2
-   frontier_baseline_goals [agent_context] 0.5476 / 21.0 / 2

## Next action
- selected next action: payload_census -- Decompose the 27-61k-token first turn into prompt, tool schema, context JSON and task, from archived transcripts and request_bytes (L0032)

Start with `BOOTSTRAP.md`, then `generation.py open`.
