---
id: bench-self-integrity
family: meta
method: ab-fixture-run
cadence: "every-release (M2+M3); quarterly (M1 mutation drill)"
cost: M
probe: benchmarks/probes/bench-self-integrity.py
probe_status: planned
results: benchmarks/meta/results/
provenance: "lens=completeness; merged_from=[]"
---

# Bench self-integrity — mutation drill, rot audit, cadence audit

**Question.** Does the bench still detect what it claims to detect — when a known defect is deliberately planted, does the owning vector go red; how many anchors/fixtures/pinned shas have rotted; and did every vector actually run at its declared cadence last cycle?

## Procedure

Three passes.

1. **M1 — Mutation drill, quarterly.** Use the frozen registry of planted defects at `benchmarks/self/defects/` — one per detection family, e.g.: re-introduce the pack-guard Write-only matcher asymmetry into `hooks/hooks.json`; delete the shared_terms injection line in `skills/karta-plan/scripts/validate_binder.py`; un-escape one serve_status sink; break one mirror byte under `.agents/skills/`; forge one done ref in the dark-status fixture.
2. Apply each planted defect to a scratch worktree of the karta repo and run ONLY the owning vector; it must go red.
3. A planted defect that passes green is a bench miss — it counts into the bench's own false-negative rate.
4. **M2 — Rot audit, every release.** Aggregate every vector's ANCHOR-LOST / ANCHOR-STALE / INCONCLUSIVE / ENV_EXCLUDED / UNLOCATABLE emissions plus pinned-sha reachability (quality-oracle-discrimination probe-cards, dark fixtures, the vendored gringotts schema fixture) into one count, checked against the shared fixture registry `benchmarks/fixtures/REGISTRY.json`. The triage threshold is committed.
5. **M3 — Cadence audit, every release.** Diff each vector's declared cadence (this spec's vectors array is the authority) against committed results files per vector. A vector with no results artifact for the cycle is reported SKIPPED by name.
6. During the build-out phase SKIPPED rows are expected and honest, never hidden.

## Metric and comparability

M1: planted-defects-detected / planted (headline, must be 100%); M2: rotted-anchor/fixture count (monotone triage, not a ratio); M3: vectors-run / vectors-due with named SKIPPED rows.

M1's denominator is the frozen planted-defect registry at `benchmarks/self/defects/`, so the headline compares like-for-like across quarters. M2 is deliberately a monotone triage count rather than a ratio, checked against the sha-pinned `benchmarks/fixtures/REGISTRY.json`, so rot cannot be diluted by adding vectors. M3's denominator is the spec's vectors array — the declared-cadence authority — and missing runs surface as named SKIPPED rows in the committed results rather than disappearing, which keeps the vectors-run / vectors-due ratio honest during build-out.

## Inputs

- `benchmarks/self/defects/` (new frozen planted-defect registry)
- all vector results directories under `benchmarks/**/results/` and `benchmarks/results/`
- `benchmarks/fixtures/REGISTRY.json` (new sha-pinned fixture manifest)
- this spec's vectors array (declared cadences)
- scratch git worktrees of the karta repo

## Seed observation (v2.21.0, 2026-07-17)

The 22 vectors defend themselves individually (per-vector anchor states, sha pins, self-tests) but nothing aggregates the rot or ever tests the bench's detection power. A bench that silently stops catching its target class is worse than none — it converts into false assurance — and with almost everything here being build-once scripts over moving repos, decay is the default trajectory. M3 is the only thing that makes 22 declared cadences observable rather than aspirational; during build-out it is also the honest SKIPPED-row reporter.
