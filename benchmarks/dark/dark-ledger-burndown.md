---
id: dark-ledger-burndown
family: dark
method: drift-diff
cadence: every-release (seeding expansion is a one-time L-cost pass; per-release run is S-M)
cost: L
probe: benchmarks/probes/dark-ledger-burndown.py
probe_status: planned
results: benchmarks/dark/results/
provenance: "lens=dark; merged_from=prose-to-enforced-ratio-ledger, dark-area-ledger-burndown"
---

# Rules and dark-area ledger burndown

**Question.** What fraction of karta's flow rules are mechanically enforced (hook or hard-exit script) versus prose-only per subsystem, and how many mapped dark areas are still present, fixed, or mutated at this release?

## Procedure

1. SEED NOW (blocking): the audit map exists only as a session artifact at `/tmp/claude-1000/-mnt-agent-storage-vader-src-karta/0fe6f672-22b7-4c17-8abe-f8084f939961/scratchpad/karta-map.json` — copy it to `benchmarks/flow/seed-map-2026-07-17.json` and commit it as provenance before anything else. If the scratchpad has expired, the seed observations embedded in the spec's vectors are the fallback seed source.
2. One-time expansion pass: the map's determinism blocks are prose paragraphs (81 scripted_checks + 107 prose_only_rules ENTRIES, not rules; no per-rule anchors, no class taxonomy), so seeding splits each entry into per-rule records `{id, subsystem, text, class in hook-fail-closed|hook-fail-open|script-hard-exit|script-prose-invoked|prose-only, anchor}`. Commit `benchmarks/flow/rules-ledger.json` + `benchmarks/flow/cards/*.yml` + `benchmarks/flow/run_dark_ledger.py`.
3. The ledger is append-only forever after: never bulk re-seed; a future re-audit adds records tagged `epoch:2` reported in a separate denominator.
4. ANCHORS: for prose rules, anchor = `{file, needle}` with needle a distinctive fixed string <=80 chars, matched by fixed-string grep after whitespace normalization (`tr -s '[:space:]' ' '`), against the canonical `skills/` + `skills/_shared/` tree ONLY (never `.agents/` or `plugins/` mirrors — check_shared_copies.py keeps them identical). For enforced rules, anchor = script path; the runner asserts existence and runs `--self-test` (all 6 `hooks/scripts/*.py` and validate_binder.py/check_shared_terms.py/detect_stack.py support it — verified).
5. Anchor-miss is verdict ANCHOR-STALE (a human re-anchors or reclassifies in the same commit as results), NOT auto-MUTATED — SKILL.md prose is rewritten every release and whole-sentence anchors rot.
6. NEW-RULE TRIPWIRE: `git diff <prev-release-tag>..HEAD -- skills/ hooks/hooks.json`, filter added lines through a regex PINNED IN THE RUNNER, e.g. `\b(MUST|must not|never|NEVER|halt|only writer|fail-closed|hard-exit)\b` (changing the regex = new epoch for this count). A human classifies each hit into the ledger or a committed not-a-rule allowlist. The run FAILS if `unclassified_new > 0` or any ANCHOR-STALE is unresolved.
7. DARK CARDS: `benchmarks/flow/cards/<subsystem>-<nn>.yml` with `{id, subsystem, claim, probe}` where probe is a shell one-liner exiting 0=FIXED, 1=STILL-DARK, 2=ANCHOR-GONE (triage). Seed the ~70 of 79 map dark areas that carry file:line evidence first (verified viable: REF_STATES at guard_delivery_stop.py:41, shared_terms absent from binder-schema.json, in-progress in integration-branch.md all reproduce today); the ~9 judgment-only areas become `probe: manual` in a separate manual denominator.
8. FIXED cards are never deleted — they gain `fixed_in:<version>` so burndown is cumulative.
9. OUTPUT: `benchmarks/flow/results/<version>-dark-ledger.json` with per-class rule counts, enforced ratio per subsystem, the (still_dark, fixed_since_last, anchor_gone) triple, and unclassified_new; the runner diffs against the previous committed results file and prints the delta.
10. HONESTY RULES in the README: the enforced ratio is an index over frozen seed records, not a true rule count; compare each subsystem only to its own history — cross-subsystem ratio comparison is invalid because seed granularity differs per subsystem.

## Metric and comparability

enforced/(enforced+prose-only) index over frozen seed records, total and per-subsystem (each subsystem compared only to its own history) + (still_dark, fixed_since_last, anchor_gone) triple + cumulative burndown + unclassified-new-rules count (run fails if >0) — compared release over release via committed ledger JSONs.

Comparability rests on the frozen seed: the ratio is an index over seed records that never get bulk re-seeded, so its denominator cannot drift; any re-audit or tripwire-regex change opens a new epoch reported in a separate denominator rather than contaminating the old one. FIXED cards keep their `fixed_in:<version>` tag instead of being deleted, making burndown cumulative, and each release's numbers are diffed against the previous committed ledger JSON. Cross-subsystem ratio comparison is explicitly invalid because seed granularity differs per subsystem.

## Inputs

- benchmarks/flow/seed-map-2026-07-17.json (committed copy of the session audit map; determinism + dark_areas for all 10 subsystems)
- skills/**/SKILL.md + skills/_shared/*.md
- hooks/hooks.json
- repo HEAD at /mnt/agent-storage/vader/src/karta
- previous release's committed ledger runs under benchmarks/flow/results/

## Seed observation (v2.21.0, 2026-07-17)

Baseline: 81/188 entries ~43% enforced overall (an index over map ENTRIES, not individual rules — one entry can bundle ~15 checks); deliver worst at 36% (9/25) with all four core merge invariants (serial FIFO, single tip writer, mandatory re-validation, ref-last ordering) plus wave/frontier computation and Phase-4 anti-forgery entirely prose-only; hooks best at 60%. Hardening velocity ~1 rule/release (2.21.0's Stop-gate moved exactly one rule), making the 107-entry prose backlog a decades-long tail at current pace. Dark side: 0 fixed, ~79 still-dark — spot probes confirm binder-schema.json still lacks shared_terms, guard_delivery_stop.py:41 still reads REF_STATES=(built,done,failed), and integration-branch.md:52 still lists the never-written in-progress ref.
