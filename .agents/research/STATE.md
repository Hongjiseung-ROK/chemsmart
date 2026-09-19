# STATE (rendered by `generation.py close`; every fact is a ledger row)

Loop **g3** (parent g2). Ledger: 51 records, chain ok.

## Components adopted on evidence
- `retrieval` (promoted, L0038,L0040,L0041): AGENTS.md is a kernel under 2,000 words and CLAUDE.md imports it, so every session starts from the same small file.
- `generate` (tested, L0001,L0018,L0026): Candidates are enumerated, not recalled: every untested component falsifier, every claim's missing experiment, every unvalidated rule annotation and e.
- `reflect` (tested, L0003,L0025): Every ledger row names the loop components responsible (attribution).
- `topology` (tested, L0002,L0034,L0040): One investigator per question, briefed with objective, boundaries and output format, and an adversarial design review before spend.
- `cascade` (promoted, L0004,L0014,L0020,L0021,L0022): L0 static, L1 archived replay, L2 provider-free, L3 planning-only live, L4 sealed goals.
- `evaluators` (tested, L0034,L0035,L0046,L0047): Exact-match keys wherever the host can know the answer.

## Decisions (newest last)
- L0043 promote: loop g1 -> g2: component `retrieval` mutated
- L0044 promote: loop g1 -> g2: component `topology` mutated
- L0045 select: selected next action: affordance_visible_investigation -- The next delegated investigation runs 
- L0048 promote: loop g2 -> g3: component `evaluators` mutated
- L0050 absorb: SCF-stability branch absorbed whole by merge 2b954d6e after a further boundary probe; its senten

## Open
- forecasts awaiting outcomes: 23 events (E02, E03, E04, E05, E06, E07 ...)
- loop components under most pressure: evaluators(10), generate(8), reflect(6), topology(5)

## Slate (EIG bits / cost units / risk)
- * payload_census [agent_context] 0.9014 / 0.1 / 0
- * affordance_visible_investigation [research_loop] 0.4345 / 0.08 / 0
-   bypass_census [product] 0.3196 / 0.16 / 0
-   stream_replay_test [product] 0.147 / 0.12 / 1
-   xtb_row_identity_guard [product] 0.1298 / 0.12 / 0
-   defect_channel_ledger [product] 0.3785 / 0.48 / 0

## Next action
- selected next action: affordance_visible_investigation -- The next delegated investigation runs with the kernel visible and a brief that names the graph and the ledger; its trace is compared with the unprimed PySCF run (0 of 169 calls into .agents/) (L0045)

Start with `BOOTSTRAP.md`, then `generation.py open`.
