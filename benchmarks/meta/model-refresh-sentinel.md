---
id: model-refresh-sentinel
family: meta
method: ab-fixture-run
cadence: "every-release (S1); event-driven on mapping change (S2 A/A canary)"
cost: S
probe: benchmarks/probes/model-refresh-sentinel.py
probe_status: planned
results: benchmarks/meta/results/
provenance: "lens=completeness; merged_from=[]"
---

# Model refresh sentinel — alias map, epochs, A/A re-baseline

**Question.** karta pins its agents by model ALIAS (plan opus/xhigh, gates opus/high, orchestrators haiku, gardner sonnet/high, codex gpt-5.4) — when the host remaps an alias to a new underlying model, does the bench notice within one cycle, quarantine cross-version comparisons, and re-baseline the LLM-driven arms so subsequent deltas are attributable to karta changes rather than model drift?

## Procedure

1. **S1 — Alias-map probe, every release and cheap.** Resolve each pinned alias to its concrete model ID (one minimal `claude -p` / `codex exec` invocation per distinct alias, reading the model ID from the transcript/meta) and diff against the committed map `benchmarks/epochs/alias-map.json`.
2. Also grep `agents/*.md` and skill frontmatter for alias/effort changes in the release diff.
3. **S2 — On any mapping change.** Mark the epoch boundary in committed `benchmarks/epochs/epochs.json`, which ALL comparison-consuming vectors must join against (perf-fixture-cost-baseline, quality-doc-gardner-recall, sme-fixture-campaign, flow-guard-enforcement-matrix Family C, and sec-untrusted-input-surfaces P3 already record model IDs — this file is the shared authority they currently lack).
4. Run the A/A canary: k=3 repeats of one pinned micro-fixture per role (one plan synthesis, one build item, one gate verdict, one gardner pass) on the new model, scored by the existing deterministic scorers, committed as the new epoch baseline. No better/worse judgment — only a new anchor.
5. **S3.** The trend runner (trend.py) flags any cross-epoch delta computed without an epoch join as INVALID and refuses to print it.

## Metric and comparability

Alias-to-model-ID map diff per release (binary changed/unchanged per alias); on change: epoch recorded + A/A baseline committed within the same cycle (binary); count of cross-epoch comparisons attempted without quarantine (must be 0).

Comparability rests on the epoch join: `benchmarks/epochs/epochs.json` is the single committed authority every comparison-consuming vector must join against, so a model refresh splits the timeline into epochs instead of silently contaminating trends. The A/A canary commits a new baseline anchor within the same cycle — explicitly no better/worse judgment, only a new anchor — and the trend runner refuses to print any cross-epoch delta computed without an epoch join, which is what keeps the must-be-0 unquarantined-comparison count enforced rather than aspirational.

## Inputs

- `agents/*.md` model/effort frontmatter + skill model pins
- `benchmarks/epochs/alias-map.json` (new committed map)
- `benchmarks/epochs/epochs.json` (new shared epoch authority)
- one pinned micro-fixture per role (plan / build / gate / gardner)
- minimal `claude -p` / `codex exec` alias-resolution invocations

## Seed observation (v2.21.0, 2026-07-17)

Five vectors independently record model IDs as a defensive footnote, but recording only lets you EXCLUDE contaminated deltas — nothing detects the refresh promptly, nothing re-baselines, and nothing stops two vectors from handling the same refresh inconsistently. After a silent opus remap, every quarterly trend in the bench is uninterpretable until someone notices manually, and karta's own field behavior (planner quality, gate strictness) shifts with no signal separating 'plugin regressed' from 'model changed' — the exact confusion the determinism doctrine exists to prevent.
