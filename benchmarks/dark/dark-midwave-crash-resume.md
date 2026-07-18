---
id: dark-midwave-crash-resume
family: dark
method: ab-fixture-run
cadence: quarterly
cost: L
probe: benchmarks/probes/dark-midwave-crash-resume.py
probe_status: planned
results: benchmarks/dark/results/
provenance: lens=dark; merged_from=midwave-crash-resume-fixture
---

# Mid-wave crash and resume fixture

**Question.** After a mid-wave worker death (built-unmerged item + zero-commit pending item + stale worktree + existing wave tags), does a resumed karta-deliver reconstruct correctly — merging without rebuilding, not double-tagging, not deleting valid refs?

## Procedure

1. Bench lives at `benchmarks/deliver/midwave-crash/` (convention: `benchmarks/<name>/` with `fixtures/`, runner, `results/`, honesty-rule README).
2. Precondition: pilot the headless `-p` deliver path once before adopting (`benchmarks/sme/README.md` notes headless automation is unproven).
3. `make_fixture.sh` builds a throwaway repo with `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` and author pinned so all fixture SHAs are byte-stable across quarters. 3-item binder, trivial file-touch items, `test -f` oracles.
4. Build TWO variants, both doctrine-reachable (`skills/karta-deliver/SKILL.md` Step 3 tags `wave-N-base` only when the merge pass starts — the draft's single fixture with `wave-2-base` + in-flight builds is an unreachable state):
   - VARIANT A (mid-build crash): wave-1 complete (`wave-1-base` + `wave-1` tags, item-a done ref at its merge commit); wave 2 dispatched — item-b built ref at unmerged item-branch tip, item-c branch with zero commits; NO `wave-2-base` tag; stale worktree for item-b; orphan stash mimicking the gringotts wave-4 scratch stash.
   - VARIANT B (mid-merge-queue crash): `wave-2-base` tagged, item-b done (merged), item-c built-unmerged, no wave-2 success tag.
5. `make_fixture.sh` emits `manifest.pre`: `git for-each-ref refs/karta/ refs/tags/` + branch tips + worktree list + stash list.
6. RUN (n=3 per variant): `CLAUDE_CONFIG_DIR=$(mktemp -d)` with the pinned plugin installed; `cd` into the fixture; run `claude -p --dangerously-skip-permissions 'karta-deliver midwave. A prior run crashed mid-wave. At the preflight resume-or-clear prompt choose RESUME — never clear.'` The explicit resume authorization is required: headless `-p` has no user-input facility and SKILL.md forbids silent resume, so an unadorned prompt dies at preflight and measures nothing.
7. Record `claude --version` + model ID in the result file.
8. ASSERT via `assert_resume.sh` diffing `manifest.post` vs `manifest.pre`, three tiers:
   - SAFETY invariants, must hold at ANY terminal state including a clean halt — S1 item-a done SHA unchanged; S2 `wave-1`/`wave-1-base` tags unmoved, no duplicate or renumbered wave tags; S3 no ref in `refs/karta/<slug>/` deleted vs `manifest.pre`; S4 item-b built tip either still at its ref or an ancestor of a new item-b done merge (merged, never rebuilt); S5 old integration tip is ancestor of new tip (no force-move).
   - PROGRESS, scored only when the run reports success — P1 item-b done exists with built tip as ancestor; P2 item-c done exists and its oracle file present at tip; P3 stale worktree pruned/reused without clobber.
   - OBSERVATIONAL, recorded not scored — O1 wave-N derivation choice (reuse-2 / increment-3 / error-on-duplicate; doctrine is silent, so this is a spec-gap probe, not pass/fail); O2 stash disposition; O3 halt-vs-complete and stated reason.
9. Kill/resume harness shared with quality-verify-integrity-drills under `benchmarks/lib/`.

## Metric and comparability

Headline = safety-invariant pass fraction over S1-S5 (target 1.0; any safety flip across releases is a regression, full stop); progress fraction over P1-P3 reported separately for runs reporting success; observational rows O1-O3 recorded not scored; raw per-assertion count table at n=3 per variant — no interval statistics.

Comparability holds because the fixture is frozen: pinned author and commit dates make all fixture SHAs byte-stable across quarters, so every release runs against the identical pre-crash state and the identical `manifest.pre`. The safety/progress split keeps scoring honest across releases — a release that correctly halts on the duplicate-tag ambiguity is not penalized against one that silently anchors wrong — and raw counts at n=3 are published as-is with no interval statistics.

## Inputs

- skills/karta-deliver/SKILL.md (Step 3/4, resume partition)
- skills/karta-deliver/references/integration-branch.md (revert-the-wave, ref lifecycle)
- benchmarks/deliver/midwave-crash/ (new: make_fixture.sh, assert_resume.sh)
- headless claude -p substrate with isolated CLAUDE_CONFIG_DIR
- field evidence: gringotts stash@{1} wave-4 crash + live browse-refinements mid-flight state

## Seed observation (v2.21.0, 2026-07-17)

Resume will likely complete the pending item (it did in gringotts), but expect failures on hygiene assertions: the stale worktree and stash survive (the gringotts scratch stash was never cleaned), and wave re-tag behavior is undefined — a run that re-derives N over existing tags will either error on the duplicate tag or silently anchor to the stale base, exposing the unspecified-N dark area (O1). The safety/progress split exists because a release that correctly HALTS on the duplicate-tag ambiguity must outscore one that silently anchors wrong.
