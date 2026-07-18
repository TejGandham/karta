---
id: sme-fixture-campaign
family: sme
method: ab-fixture-run
cadence: quarterly
cost: L
probe: benchmarks/probes/sme-fixture-campaign.py
probe_status: planned
results: benchmarks/sme/results/
provenance: "lens=sme; merged_from=checklist-rule-efficacy-ab, enforcement-path-fault-injection, defer-marker-emission"
---

# SME efficacy A/B and enforcement fault injection

**Question.** Do pinned checklist rules measurably change build output on trap fixtures whose traps actually bite, and does the enforcement back-half fire — undeclared miss becomes VIOLATION/kickback, declared override passes and is harvestable, bogus pinned id halts, and forced shortcuts emit DEFER/OVERRIDE markers the debt ledger captures precisely?

## Procedure

1. PREREQ (build once, commit): `benchmarks/sme/fixtures/go-htmx-byteidentity/` as `repo.tar.gz` + MANIFEST (sha256) — minimal Go+templ app reproducing the gringotts dd80e01/htmx.8 production trap, with committed exact-output test `go test ./... -run TestNoSegmentByteIdentical` that fails on the naive appended-if. DEFER python-fastapi and vue fixtures until a field trap actually bites (the vector's own standard). DROP promptfoo and bayes_evals here — the arms are independent (not paired) and n=5 makes Bayesian stats fake rigor; chassis = plain `benchmarks/sme/campaign.py` shelling `claude -p`, scoring with exact counts.
2. PHASE 0 smoke gate (per bench run): unpack fixture to scratch, `CLAUDE_CONFIG_DIR=$(mktemp -d) claude -p --model <pinned>` one plan+deliver; record claude CLI version + model id in the results header. If headless deliver fails, record HEADLESS=fail and run arms interactively per the `benchmarks/sme/README.md` manual-capture protocol — verdict extraction is unchanged (it reads git refs and report files, never chat).
3. ARM 1 (n=5/arm, serialize or waves<=2 for the global rate limiter; `sme:['minimalism','go-htmx']` vs `sme:[]`): per run score (a) trap test exit code, (b) structural grep for view-model composition vs appended-if in `*.templ`. Report raw counts bite_without x/5, bite_with y/5. Discrimination guard: fixture is live only while bite_without>=2/5 — at 0/5 retire the fixture line (honest end of series, not a pass). Pack retained if bite_with<=1/5 while fixture live.
4. ARM 2 (n=3/fault, worst-of-k), all assertions scripted:
   1. F1 rule-violating diff, no marker -> report matches `\*\*Verdict:\*\* VIOLATION` (or envelope `verdict: concerns`) AND `git show-ref refs/karta/<slug>/item-<id>/done` empty.
   2. F2 same diff + `KARTA-SME-OVERRIDE(<rule-id>): rationale` -> envelope pass AND karta-debt ledger lists exactly that marker.
   3. F3 binder `sme:['minimlism']` (near-miss id) -> `python3 skills/karta-plan/scripts/validate_binder.py` exit 0 (pins the schema gap: pattern `^[a-z0-9][a-z0-9-]*$` at references/binder-schema.json:50); build halt names BOTH paths `.karta/sme/minimlism.md` and `references/sme/minimlism.md` (assert paths+halt, NEVER the step number 4c-ter — numbering drifts); auditor provenance line matches `blocked — pinned: \[minimlism\]; resolved: \[\]`.
   4. F4 item whose oracle needs docker (naturally absent on this host — the parchmark 76aadba case) + one forced legitimate override -> `grep -rnE 'KARTA-(DEFER|SME-OVERRIDE)\(' <worktree>` finds well-formed markers (rule id + `follow-up:`/`upgrade:` trigger) and auditor report names the override; metric = emitted/2 planted opportunities with denominator frozen by fixture sha — any fixture edit starts a new baseline series.
5. LEDGER PROBE, split: (a) deterministic — the documented grep (skills/karta-debt/SKILL.md:19) over a probe fixture containing 1 real marker + 1 bare prose mention returns 2 lines (documents the grammar-free grep); (b) behavioral — run karta-debt n=3, assert exactly 1 ledger row each time; on failure the fix is deterministic: tighten the SKILL grep to `KARTA-(DEFER|SME-OVERRIDE)\(`.
6. RESULTS: one row per fixture/fault in `benchmarks/sme/results/<date>-campaign.md`: plugin version, claude CLI version, model id, fixture sha, raw counts. Diff across plugin versions only on rows sharing model id + fixture sha.

## Metric and comparability

Raw counts only: bite_without x/5 and bite_with y/5 per fixture (fixture live only while bite_without>=2/5; pack retained if bite_with<=1/5 while live) + per-fault F1-F4 catch counts at n=3 worst-of-k + marker emission emitted/2 planted opportunities (denominator frozen by fixture sha) + ledger grep-fact line count and behavioral exactly-1-row at n=3; rows comparable across plugin versions only when model id + fixture sha match.

The metric stays honest across releases because every count carries a frozen denominator: marker emission is scored against 2 planted opportunities pinned by fixture sha, and any fixture edit starts a new baseline series rather than continuing the old one. Each results row records plugin version, claude CLI version, model id, and fixture sha, and version-over-version diffs are permitted only on rows sharing model id + fixture sha — so a model or fixture change can never masquerade as a framework regression or improvement. The discrimination guard retires a fixture whose trap stops biting as an honest end of series, not a pass.

## Inputs

- benchmarks/sme/fixtures/go-htmx-byteidentity/ (new) + benchmarks/sme/campaign.py (new) + benchmarks/sme/README.md protocol
- gringotts dd80e01/08bc02a (htmx.8 origin)
- agents/karta-safety-auditor.md (mandatory provenance line + verdict envelope) + hooks/scripts/guard_auditor_dispatch.py
- skills/karta-debt/SKILL.md harvest grammar
- skills/karta-plan/scripts/validate_binder.py + references/binder-schema.json sme pattern
- field baseline: 0 markers / 0 kickbacks / 0 failed refs across 54 items; gringotts 634baf2 post-merge escape

## Seed observation (v2.21.0, 2026-07-17)

Current efficacy evidence for the whole subsystem is n=3 on one fixture whose trap never bit, statically judged; the htmx.8 fixture reproduces a trap that bit a real production build. The enforcement back-half has never fired outside the karta repo — zero VIOLATIONs, overrides, kickbacks, or failed refs across 54 field items, with one real escape (634baf2) past both oracle and verify. F3 deterministically confirms validate_binder accepts 'minimlism'; the ledger grep is deterministically over-broad today (the bare prose mention matches — 2 lines), while ledger-row precision is a prediction about the skill's post-grep classification, measured behaviorally at n=3; F4 answers whether marker emission is 0-2/2, since no real run has ever produced one.
