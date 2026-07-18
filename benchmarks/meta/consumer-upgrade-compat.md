---
id: consumer-upgrade-compat
family: meta
method: deterministic-probe
cadence: every-release
cost: M
probe: benchmarks/probes/consumer-upgrade-compat.py
probe_status: planned
results: benchmarks/meta/results/
provenance: "lens=completeness; merged_from=[]"
---

# Consumer upgrade compatibility — old artifacts under new readers

**Question.** When the karta plugin advances, do consumer repos carrying artifacts from OLD versions still work — do historical binders (live and archived, including known old-format instances like the sme-less note-edit-save-workflow.json), historical ref layouts, and old marker/commit grammars still validate, derive status, render in watch, and satisfy the Stop-gate under the NEW version — and when a format tightens, is there a stated migration path instead of silent breakage?

## Procedure

1. Freeze a compatibility corpus once at `benchmarks/compat/corpus/` (append-only), and grow it every release: copy every distinct historical binder shape from parchmark/gringotts (per-era partitions already identified by sme-pack-static-suite: pre-sme, pre-shared_terms, pre-surface, current — including the sme-less archived note-edit-save-workflow.json) plus a git fixture reproducing each era's ref/tag/marker layout.
2. Per release, run the NEW version's readers over the corpus, as steps 3-7.
3. `skills/karta-plan/scripts/validate_binder.py`: archived binders must at minimum not crash and must be classified, not rejected as corrupt.
4. `skills/karta-status/scripts/karta_next.py --json`: derives a state for every era, no silent vanishing — the corrupt-binder-silently-skipped path is a known trap, cross-checked by dark-status-surface-probes S5.
5. serve_status self-render: era rows render.
6. `hooks/scripts/guard_delivery_stop.py` payloads over old ref layouts: no false block/false pass.
7. The karta-debt harvest over legacy marker grammar: legacy-format detection is already promised in that skill.
8. Any schema/vocab tightening in the release diff must ship either corpus-green readers or a migration note + version-guarded acceptance; absence of both = red.
9. Emit the era-by-reader matrix to `benchmarks/compat/results/<version>.json`.

## Metric and comparability

Corpus cells (era x reader) pass/fail matrix; headline = new-version regressions on previously-green cells (must be 0 without a committed migration note). Corpus is append-only; new eras enter at their first release, never backfilled as failures.

The append-only corpus is the frozen denominator: every release runs its readers over the same accumulated era fixtures, so a cell that was green can only go red because the new version changed a reader. New eras enter the matrix at their first release and are never backfilled as failures, so the headline regression count compares each release only against cells that were actually green before, and the per-version results file at `benchmarks/compat/results/<version>.json` keeps each release's matrix separately attributable.

## Inputs

- `benchmarks/compat/corpus/` (new, append-only: era-partitioned binder shapes from parchmark/gringotts + per-era ref/tag/marker git fixtures)
- `skills/karta-plan/scripts/validate_binder.py`
- `skills/karta-status/scripts/karta_next.py` + `serve_status.py`
- `hooks/scripts/guard_delivery_stop.py`
- `skills/karta-debt` (legacy marker grammar)
- the release diff (schema/vocab tightening detector)

## Seed observation (v2.21.0, 2026-07-17)

binder-schema.json is additionalProperties:false and the archive is forever ('slug retired forever'), so every schema tightening is a landmine under parchmark's existing archive; one instance already surfaced as the sme-less archived binder distorting denominators. Field vectors audit repos against CURRENT doctrine only — nobody asserts old artifacts survive the upgrade, and status's failure mode for unparseable binders is silent disappearance, meaning an upgrade break would present as work ceasing to exist rather than an error.
