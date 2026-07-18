---
id: perf-context-latency-floors
family: perf
method: deterministic-probe
cadence: every-release
cost: M
probe: benchmarks/probes/perf-context-latency-floors.py
probe_status: planned
results: benchmarks/perf/results/
provenance: "lens=perf; merged_from=context-budget-probe, latency-floor-probe"
---

# Context budget and deterministic latency floors

**Question.** How many bytes/estimated tokens of skill+reference text does each karta phase force into a session (does any always-loaded file exceed the Read cap?), how much of the loaded set is duplicated — and what fixed latency do hook chains, the precommit gate, status derivation, and SessionStart injection impose on ordinary actions?

## Procedure

1. Two probes, one dated JSON committed to `benchmarks/perf/results/YYYY-MM-DD.json`; the first run bootstraps budgets, later runs diff against ABSOLUTE budgets committed in `scenarios.json` (never against the previous run — a vs-previous check is a compounding ratchet).
2. PROBE 1 — `benchmarks/perf/context_budget.py` + hand-authored `benchmarks/perf/scenarios.json`: each scenario's (build-lean, build-ui, plan-ui, plan-policy, deliver, verify-full, validate, status) always-loaded set is derived from the SKILL.md texts and pinned in scenarios.json (the audit map's context_cost fields were session prose, not a committed input). The script FAILS if `grep -oE 'references/[A-Za-z0-9_.-]+\.md' plugins/karta/skills/*/SKILL.md` names a file absent from scenarios.json (no silent drift of the loaded set).
3. Per file record bytes, lines, est tokens = bytes/3.8 (trend-only, never an assertion — the estimator and the real Read cap disagree: 78,273-byte karta-build/SKILL.md scores ~20.6k estimated tokens yet truncates in reality).
4. Hard assertions: (a) no always-loaded file > 55,000 BYTES — calibrated to the observed Read-cap truncation of karta-build/SKILL.md at line 383 (= 56,297 bytes); recalibrate the byte cap only if the harness cap changes, with a note in scenarios.json; (b) per-scenario total bytes <= its committed absolute budget; budget edits require a rationale line in the commit.
5. Duplication: fraction AND absolute count of lowercased whitespace-collapsed 8-word shingles appearing in >1 loaded file, per scenario, with the top-5 offending file pairs named.
6. PROBE 2 — `benchmarks/perf/latency_probe.sh`: for each matcher entry in `hooks/hooks.json` (repo root — NOT plugins/karta/hooks/, which does not exist) pipe checked-in synthetic payloads (`benchmarks/perf/payloads/`: binder-write.json, pack-write.json, confined-write.json, stop.json) into each guard script; 21 reps, discard rep 1, report min and median ms; floor assertions on MIN (min > 300 ms per guard fails; per-Write chain = sum of the 3 PreToolUse guard mins + PostToolUse) — min-of-N because wall-clock medians on this shared host (Incus VMs, browsers) are noisy.
7. Time `uv run scripts/validate_plugin.py` end-to-end (fails > 5 s) and one docs-only commit in a scratch clone with hooks installed (fails > 5 s).
8. karta_next scaling: generate synthetic repos B in {1,10,50} x 5 items (script writes `refs/karta/**` + binder JSONs); PRIMARY metric = exact git-subprocess count per `skills/karta-status/scripts/karta_next.py` run, captured by a PATH shim that increments a counter file then execs real git — assert the counts fit count = a + b*B exactly across all three B (integer, deterministic; breaks the moment anyone adds a per-binder or per-item extra call); wall time at each B recorded as secondary with no assertion.
9. Time `hooks/scripts/inject_karta_status.py` at B=10 (min-of-21, 300 ms floor).

## Metric and comparability

Per-scenario bytes vs committed absolute budgets + 55,000-byte always-loaded-file cap pass/fail + duplication ratio and absolute count with top-5 offending pairs; per-guard/chain/commit-gate/injection floors on min-of-21 ms against fixed thresholds; karta_next git-subprocess count must fit count = a + b*B exactly at B=1/10/50 (primary), wall time secondary unasserted.

The metric stays honest across releases because every assertion runs against fixed, committed reference points: absolute budgets in scenarios.json rather than the previous run (which would compound as a ratchet), a byte cap calibrated to the observed harness Read cap and recalibrated only when the harness changes with a note in scenarios.json, and budget edits that require a rationale line in the commit. The grep-based drift check fails the run when a referenced file is missing from scenarios.json, so the loaded set cannot silently shrink or grow. Latency floors assert on min-of-21 (deterministic lower bound on this noisy shared host), and the karta_next primary metric is an exact integer subprocess count rather than wall time, so it cannot drift with host load.

## Inputs

- plugins/karta/skills/*/SKILL.md + references/*.md
- benchmarks/perf/scenarios.json (new, hand-authored; replaces the audit map's context_cost prose)
- hooks/hooks.json (repo root) + hook scripts
- scripts/validate_plugin.py
- skills/karta-status/scripts/karta_next.py + hooks/scripts/inject_karta_status.py
- benchmarks/perf/payloads/ (new checked-in synthetic payloads)
- benchmarks/perf/results/ prior runs

## Seed observation (v2.21.0, 2026-07-17)

Fails today: karta-build SKILL.md is 78,273 bytes and truncates at the Read cap (56,297 bytes through line 383) — an enforced silent degradation; note the bytes/3.8 estimator would NOT catch this (~20.6k est. tokens), which is why the cap is asserted in bytes. Baselines: build-lean ~1,006 lines (~50k est. tokens) before touching project code; deliver's duplication ratio flags the verbatim double 5-gate table and 4x-restated single-writer rule. Latency: validate_plugin ~2.4s on every karta-repo commit (guard_delivery_stop.py:310 builds TemporaryDirectory git fixtures inside its --self-test, re-run as subprocesses), consumer Write/Edit pays up to 3 sequential python forks (confirmed in hooks.json), and karta_next's O(2B+2I) subprocess pattern is re-paid every 2.6s per watch client — the B=50 probe makes the growth visible.
