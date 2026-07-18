---
id: release-gate-blocking-smoke
family: meta
method: deterministic-probe
cadence: every-release (pre-tag, blocking; artifact audit retroactive)
cost: S
probe: benchmarks/probes/release-gate-blocking-smoke.py
probe_status: planned
results: benchmarks/meta/results/
provenance: "lens: completeness; merged_from: none"
---

# Release gate — blocking pre-tag deterministic lane

**Question.** Before a karta release is tagged, does a blocking pre-tag run of the deterministic bench lane actually execute on the release-candidate commit and halt the release on any red — so a broken guard, validator, or sync script cannot ship — and is the verdict artifact committed alongside the version bump?

## Procedure

1. Define the gate lane as the S-cost deterministic subset: `scripts/validate_plugin.py`, all guard `--self-tests` plus flow-guard-enforcement-matrix Families A+B, flow-spec-contradictions, sme-pack-static-suite, parity-mirror-sync-integrity, parity-doc-truth-ledger, dark-status-surface-probes fixture states, quality-verify-integrity-drills Layer 0 static tripwires, sec-untrusted-input-surfaces P1/P2.
2. Ship one entrypoint (`benchmarks/gate/run_gate.py`, python3 stdlib, no node/promptfoo dependency) that runs the lane against the RC worktree, writes `benchmarks/gate/results/<version>.json` (per-vector verdicts + RC sha + wall-clock), and exits nonzero on any red.
3. Enforce, don't hope: extend the existing repo precommit gate to block any commit that bumps the plugin version in `.claude-plugin/plugin.json` unless a results file for that exact RC sha exists and is green (same pattern as the delivery Stop-gate — mechanical halt, not checklist prose).
4. Self-check: the vector also audits past releases — for each version tag, does a committed green gate artifact exist whose sha matches the tagged commit?
5. Assert the wall-clock of the lane against a committed budget (proposed <10 min; see open_questions).

## Metric and comparability

Per-release binary: gate-artifact-exists-and-matches-RC-sha. Trend: releases-with-green-gate / releases since vector adoption (must be 100%); gate lane wall-clock vs the committed budget.

Comparability rests on the sha binding and a frozen denominator: the artifact must match the exact RC sha, so a green result cannot be borrowed from a neighboring commit, and the trend ratio is computed over releases since vector adoption, so early un-gated history cannot dilute or inflate it. The retroactive audit of version tags against committed artifacts makes any skipped gate visible after the fact, and the wall-clock is judged against a committed budget rather than a drifting informal expectation.

## Inputs

- benchmarks/gate/run_gate.py (new)
- scripts/validate_plugin.py + hooks/scripts/guard_*.py --self-tests
- the deterministic vector runners it composes (see procedure list)
- the repo precommit gate (extended with the version-bump block)
- karta release tags + .claude-plugin/plugin.json history

## Seed observation (v2.21.0, 2026-07-17)

Sixteen of the 22 vectors declare every-release cadence but nothing defines WHEN relative to tagging, what is blocking, or where the verdict lives — the exact skippable-prose failure mode the owner built hooks to eliminate in karta itself. Without this, the bench is a post-mortem instrument: a broken guard ships to parchmark/gringotts and the bench documents it a release later. Retroactive audit baseline: no release to date has a committed gate artifact (0%). Cheapest vector in the set to build (a runner + one precommit rule); it converts the whole deterministic lane from advisory to enforced. Build first, together with bench-self-integrity M3.
