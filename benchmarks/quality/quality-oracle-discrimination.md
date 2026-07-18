---
id: quality-oracle-discrimination
family: quality
method: field-audit
cadence: "every-release (static steps + host-runnable replays); on-demand (ENV_EXCLUDED replays via Incus Docker staging)"
cost: M
probe: benchmarks/probes/quality-oracle-discrimination.py
probe_status: planned
results: benchmarks/quality/results/
provenance: "lens: quality; merged_from: oracle-discrimination-rate, oracle-discrimination"
---

# Oracle discrimination and degeneracy audit

**Question.** Do the oracle commands that certify karta items actually discriminate the item's change (fail before the work existed, pass after), or do they collapse into one repo-wide gate — and do oracles get silently downgraded mid-stream when the environment can't run them?

## Procedure

Tooling: `benchmarks/output-quality/oracle_discrimination.py` (python3 stdlib + git; no LLM judge). Run per corpus (karta, parchmark, gringotts binder archives):

1. LOCATE, ONCE: resolve each certified item's pre/post trees in fixed priority — `refs/karta/<binder>/<item>/done` -> `karta/<binder>/wave-N-base` tag -> parent of first commit matching `git log --reverse --grep='\[karta:item-<id>\]'`; emit `{item: {pre_sha, post_sha, method}}`. If a committed probe-card already pins shas for a binder, reuse them verbatim — never re-locate (guards against ref decay changing the denominator). Report locatable-rate as a first-class stat.
2. REPLAY: `git worktree add` at pre_sha, run `oracle.command` under `timeout 600` capturing exit code + first stderr line; same at post_sha; one retry on any FAIL, record flake if it flips. Classify per item into a 6-state enum: DISCRIMINATING_BEHAVIORAL (pre fails on an assertion, post passes), DISCRIMINATING_TRIVIAL (pre fails with exit 127/'No such file'/'not found', post passes — file-existence, not behavior), DEGENERATE (pass/pass), ROTTEN (post fails), ENV_EXCLUDED (command matches a docker|testcontainers|compose denylist — listed + counted, replayed only on-demand via the incus vader-incus-docker-host staging pattern in `~/AGENTS.md`), UNLOCATABLE. Headline rate counts BEHAVIORAL only; TRIVIAL reported separately.
3. DEGENERACY (static, S): normalize commands (collapse whitespace, strip item-name args); per-corpus distinctness ratio, modal-command share, gate-degeneracy count when modal share >40% (threshold versioned in-script).
4. DOWNGRADE (static, S): enumerate every committed version of each binder JSON via `git log --all --follow --diff-filter=ACMRD` + `git cat-file`; diff `oracle.type`/`command` keyed by item id along e2e>integration>unit>smoke; ALSO flag same-commit item delete+add pairs (re-plans like parchmark 76aadba) where a removed item's `oracle.type` outranks all added items with overlapping touches — 'replan-demotion, manual review'. Dedupe findings by (sha,item); release metric = new-since-last-card only; cumulative list kept in the card body.
5. COMPARABILITY: per-binder scores frozen at first full replay and never recomputed; release-over-release compares newly archived binders' scores + new downgrade findings + distinctness trend; never emit one blended % across corpora.

Cadence split: steps 3-4 every release (S); step 2 every release for host-runnable oracles, ENV_EXCLUDED replays on-demand. Probe-card JSON committed per run.

## Metric and comparability

Headline discriminating rate = DISCRIMINATING_BEHAVIORAL / locatable certified items, per corpus (TRIVIAL reported separately) + locatable-rate + distinctness ratio + modal-command share / gate-degeneracy count + new-since-last-card downgrade findings (sha-deduped; replan-demotion pairs flagged for manual review) + duplicate-command rate; per-binder scores frozen at first full replay; never one blended % across corpora.

The metric stays honest across releases because the denominator is guarded: shas pinned in a committed probe-card are reused verbatim and never re-located, so ref decay cannot silently shrink or shift the item set, and locatable-rate is itself reported first-class. Per-binder scores are frozen at first full replay and never recomputed, so release-over-release movement can only come from newly archived binders, new (sha,item)-deduped downgrade findings, and the distinctness trend. Corpora are never blended into one percentage, keeping attribution per-cohort, and the gate-degeneracy threshold is versioned in-script.

## Inputs

- `/mnt/agent-storage/vader/src/karta/.karta/binders/archive/*.json`
- `/mnt/agent-storage/vader/src/parchmark` (archived binders + git history)
- `/mnt/agent-storage/vader/src/gringotts` (archived binders + git history)
- `refs/karta/**/{built,done}` + wave tags where surviving
- `benchmarks/flow/seed-map-2026-07-17.json` evidence-subsystem gap (0 integration / 15 near-identical smoke oracles in karta's own corpus)

## Seed observation (v2.21.0, 2026-07-17)

karta's own corpus scores worst: 13 of 15 smoke commands are the identical repo-gates invocation and all 3 e2e commands pass on any healthy pre-item tree ('codex --version && gates'), so expect ~5-8/23 discriminating; coverage itself surfaces that only 4 of 6 archived binders retain refs (locatable-rate matters). parchmark: 1 confirmed silent downgrade (76aadba retargeted both service-layer oracles from testcontainers pytest to a lint+type floor because workers lack Docker — a replan-demotion the id-keyed diff alone would miss) and e2e 0/40. gringotts: healthiest distribution (4u/9i/1e) but low distinctness — every command is the same templ+vet+test+build gate with per-item tests appended — and the item behind the 634baf2 hand-fix certified green while the *fs.PathError bug shipped.
