---
id: quality-doc-gardner-recall
family: quality
method: ab-fixture-run
cadence: quarterly
cost: "M (one-time fixture build; S per run thereafter)"
probe: benchmarks/probes/quality-doc-gardner-recall.py
probe_status: planned
results: benchmarks/quality/results/
provenance: "lens: quality; merged_from: doc-gardner-fidelity, gardner-self-recall"
---

# Doc-gardner recall, overreach, and envelope honesty

**Question.** When doc-gardner runs, does it correct exactly the drift that exists — recall across all five doctrine drift kinds, zero overreach on immune docs, and a truthful envelope/commit — on a planted fixture with frozen ground truth?

## Procedure

Single arm: frozen planted fixture only (the draft's self-run-on-karta arm is severed — its moving-HEAD ground truth belongs to parity-doc-truth-ledger; the v1.10.0 backlog canary is an adoption fact and moves to field-feature-adoption-ledger).

1. One-time build committed at `benchmarks/fixtures/gardner/`: a builder script (`make_repo.py`) that git-inits a scratch repo, commits a base tree, then applies one 'delivery' commit touching fixture code — rebuilt fresh every run so runs share no state.
2. Plant 15 facts, each tagged by doctrine kind AND by which pass should catch it: K1 broken-pointer x3 (renamed path, removed CLI option, renamed symbol; score = stale string absent AND truth string present, exact match); K2 stale-description x4 (stale flag, wrong count, stale version, changed default; 2 inside the delivery diff, 2 outside it — the outside pair is scored as a separate 'blast-radius' sub-score, not in the primary, because only the diff pass can catch behavior drift whose pointer still resolves: this localizes the known no-shell defect at `agents/karta-doc-gardner.md:4` tools frontmatter vs `:26` 'run git diff'); K3 future-tense-landed x2 (score = marker phrase 'will add'/'planned' absent from the file); K4 speculative/derivable x2 (score = planted span absent AND pre-registered anchor sentences still present); K5 coverage-gap x2 (delivered code adds a flag + config key no doc mentions; score = token present anywhere in the doc surface).
3. All non-planted fixture prose is authored to pass the doctrine, so any diff hunk not overlapping a planted span or a gap-close counts as an overreach hunk. Immune hard gate = ONLY the dated archival paths `docs/specs/2025-01-15-*.md` and `docs/design-docs/2025-02-01-*.md` byte-identical (the doctrine's `:49` dated-archival contract; changelogs are ordinary surface, NOT immune).
4. Run k=3: `claude -p --permission-mode acceptEdits --output-format json --system-prompt "$(cat skills/karta-doc-gardner/references/karta-doc-gardner.agent.md)" 'Repo root: <scratch>. Diff range: <base_sha>..HEAD (delivery blast radius). No focus note.'` — the bundled agent file is the designed portable path (`skills/karta-doc-gardner/SKILL.md:37`), removing plugin-enablement variance.
5. Score with `benchmarks/fixtures/gardner/score.py` (python3, deterministic, no LLM judge): extracts the yaml envelope, computes per-kind recall + primary recall /13, blast-radius sub-score /2, overreach hunk count, immune byte gate, envelope-delta = |corrected_count minus changed doc FILES via `git status --porcelain`| (matches the `:83` files contract — corrected_count counts FILES, not facts). Report median primary recall, max overreach, max envelope-delta.
6. Record the resolved model ID from run JSON; if it differs from the previous bench, re-run the previous plugin tag once (A/A) before attributing deltas (join `benchmarks/epochs/epochs.json`).
7. Label check, k=1, separate: same fixture with `.karta/doc-gardner.json` `{enabled:true}`, run the skill path headlessly with an explicit 'Mode: delivery' instruction (default mode is ad-hoc = no commit, `SKILL.md:29`), assert exactly one new commit matching `'^docs: gardner '` with the envelope summary in the body.

## Metric and comparability

Median primary recall /13 (facts catchable by the pointer pass) + blast-radius sub-score /2 (diff-pass-only facts, reported separately) + max overreach hunk count (hard gate: >0 = FAIL regardless of recall) + immune byte-identity gate on the two dated archival files + max envelope-delta (|corrected_count minus changed doc FILES|) + delivery-mode label binary — compared release-over-release at matching resolved model ID (A/A re-baseline on model change).

The metric stays honest across releases because the denominator is frozen: 15 planted facts with fixed per-kind scoring rules, split into a primary /13 and a blast-radius /2 so the known no-shell defect cannot dilute or inflate the headline number. The fixture is rebuilt fresh every run from a committed builder so runs share no state, the scorer is deterministic with no LLM judge, and envelope-delta compares against the FILE-count contract (`agents/karta-doc-gardner.md:83`) so fact-count mismatches cannot produce false dishonesty findings. Release-over-release comparison happens only at matching resolved model ID, with an A/A re-run of the previous plugin tag joined against `benchmarks/epochs/epochs.json` before any delta is attributed.

## Inputs

- `benchmarks/fixtures/gardner/` (new: `make_repo.py` + `score.py`)
- `agents/karta-doc-gardner.md` (tools frontmatter :4, blast-radius step :26, envelope shape :82-87)
- `skills/karta-doc-gardner/SKILL.md` (mode default :29, commit rule :51, immunity :49, portable agent path :37)
- `skills/karta-doc-gardner/references/karta-doc-gardner.agent.md` (bundled portable system prompt)
- `benchmarks/epochs/epochs.json` (model epoch authority)

## Seed observation (v2.21.0, 2026-07-17)

Expect degraded recall: the agent's blast-radius step is unexecutable as written (told to run git diff but its frontmatter grants Read/Glob/Grep/Edit only — no shell), so scope is improvised and drift outside the guessed radius is systematically missed; the blast-radius sub-score isolates exactly this defect. envelope corrected_count has never been validated against actual edits — and it is defined as a FILE count (agents/karta-doc-gardner.md:83), so fact-count comparisons would produce false dishonesty findings. Field prior: gringotts' gardner went 3/3 on coverage but nothing ever measured what it changed.
