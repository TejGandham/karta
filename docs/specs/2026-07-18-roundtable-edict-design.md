# Roundtable edict for karta-on-karta — design

**Date:** 2026-07-18
**Status:** design, ready to plan
**Scope:** house-only tooling for the karta repo's own development. Nothing here ships in the plugin.

## Problem

When karta builds karta, the highest-leverage review happens before code exists — at the binder — and again on the assembled integration branch before it lands on `main`. This session proved the value directly: a multi-model roundtable critique of the `bench-probe-buildout` binder caught real design defects (field-lane oracles gating on live consumer repos, a six-way serialization on one registry file, a placeholder-path trap) before a single line was built.

That review was run by hand. The maintainer wants it to be an **edict, not a suggestion**: karta's own binders and deliveries may not proceed without a recorded multi-model review. This matches karta's standing doctrine — enforced checks over skippable prose.

## Constraint that shapes everything

This is for **karta building karta, not for plugin distribution**. So it must stay out of the shipped surface: no edits to `skills/`, `agents/`, or `hooks/hooks.json` (all mirrored to `.agents/`, `.claude/skills/`, `.codex/`, `plugins/` and shipped to consumer repos). It lives only in the karta repo's non-distributed surfaces — the same places the existing dev-repo commit gate already lives:

- `scripts/hooks/precommit_gate.py` — a repo-local hook, wired through the karta repo's own `.claude/settings.json`, never part of the plugin manifest.

The roundtable edict follows that exact precedent.

## The honest enforcement boundary

Roundtable is external and nondeterministic — different models, different runs, opinions that vary. A deterministic hook therefore **cannot** gate on *"the panel returned COMMIT-READY."* What it can gate on, deterministically, is **"a fresh roundtable review of this exact artifact exists and was recorded."**

So the edict is: **you may not commit a karta binder, or land a karta integration branch on the default branch, without having run the panel and recorded its findings for that exact content.** The maintainer still reads the findings and decides what to act on. Skipping the panel is what's blocked — not disagreeing with it.

This is the same shape as the `release-version-bump-block` item built this cycle: a commit is blocked unless a matching artifact exists for the exact sha. Enforce *presence of a fresh review*; keep the nondeterministic verdict out of the hard gate.

## Where it applies

The four insertion points the maintainer named split by whether a deterministic git event exists to hang an edict on:

| Point | Git event | Treatment |
|-|-|-|
| Plan (binder) | commit staging `.karta/binders/<slug>.json` | **enforced edict** |
| Deliver (integration branch) | merge/commit landing `karta/<slug>/integration` onto the default branch | **enforced edict** |
| Verify (a built diff) | none (read-only fresh session) | helper-available |
| Standalone (ad hoc) | none (on demand) | helper-available |

Plan-commit and deliver-merge have a real commit to block. Verify and standalone have no commit or stop moment, so they get the same one-command helper without a hard gate.

## Architecture

Four pieces, all in non-distributed repo surfaces.

### 1. Config — `.karta/roundtable.json`

House switch and panel settings. Because consumer repos never carry this file, the edict is karta-on-karta by construction.

```json
{
  "enabled": true,
  "tool": "roundtable-critique",
  "providers": [],
  "focus": "",
  "points": { "plan_commit": true, "deliver_merge": true }
}
```

`enabled: false` (or an absent file) disables every gate — the switch is absolute, matching the doc-gardner/kaizen opt-in pattern. `providers: []` means the panel default. `points` lets either edict be turned off independently.

### 2. Review record — `.karta/roundtable/<key>.json`

The artifact the hook checks. One per reviewed target.

- **key** — for a binder, its slug (`<slug>.json`); for a branch, `branch-<tip-sha>.json`.
- **reviewed_hash** — for a binder, a content hash of the binder file bytes; for a branch, the integration tip sha. This is what makes the record *fresh*: any change to the binder or any new commit on the branch changes the hash and invalidates the record.
- **tool**, **target_kind**, **target_ref**, **run_at**, **config_snapshot**.
- **panel** — the recorded verdicts: a list of `{provider, verdict, summary}`. A record with zero real panelist responses is not a review and does not satisfy the gate.

Records are committed (they are the audit trail that the review happened) and live under `.karta/roundtable/`.

### 3. Helper — `scripts/roundtable/run_review.py`

Stdlib-only, argparse, `--self-test`, house pattern. Roundtable itself is an MCP server the agent calls, not a CLI a script can invoke — so the helper is the **record writer and checker**, and the doctrine is: the agent runs the roundtable MCP tool, then pipes the panel result to the helper.

- `--record --target <binder-path|branch-name> [--kind binder|branch]` — reads the panel JSON on stdin, computes the key and `reviewed_hash`, writes `.karta/roundtable/<key>.json`. Rejects an empty panel.
- `--check --target <...>` — exit 0 if a fresh matching record exists, non-zero otherwise. This is what the hook calls.
- `--self-test` — `[PASS]/[FAIL]` lines and an `N/N checks passed` summary.

### 4. Enforcement hook — `scripts/hooks/roundtable_gate.py`

Stdlib-only PreToolUse/Bash hook, modeled on `precommit_gate.py`, wired in `.claude/settings.json` (not `hooks/hooks.json`). Two detections, both by git plumbing — never by parsing a diff:

- **Binder-commit gate.** When the command is a `git commit` and `.karta/binders/<slug>.json` is staged (`git diff --cached --name-only`), require a fresh record for that slug whose `reviewed_hash` matches the staged binder blob. Missing or stale → block (exit 2) with a reason naming the helper command and the escape hatch.
- **Integration-merge gate.** When the command would land a `karta/<slug>/integration` branch onto the default branch (a `git merge` naming it, or a commit on the default branch that makes the integration tip an ancestor), require a fresh `branch-<tip-sha>.json` record for the tip being landed. Missing or stale → block with a reason.

Both share `precommit_gate.py`'s stance: **fail-open** on any internal error (a broken hook must never wedge the repo), and an escape hatch **`KARTA_SKIP_ROUNDTABLE=1`** (command text or environment) for when the roundtable environment is down or a deliberate partial commit is needed. The hook ships a `--self-test`.

### 5. Doctrine — `AGENTS.md` + `docs/how-to/roundtable.md`

`AGENTS.md` states the edict, names the tool per point, and shows the run-the-panel-then-record flow and the escape hatch. `docs/how-to/roundtable.md` is the operator guide.

## Flow, end to end

**Plan.** karta-plan drafts and validates the binder → the agent runs `roundtable-critique` on the binder and pipes the result to `run_review.py --record` → the maintainer reads the findings, edits the binder if warranted (which invalidates the record, forcing a re-review) → on the `commit` verb, the binder-commit gate confirms a fresh matching record exists and allows.

**Deliver.** The wave loop assembles the integration branch → before landing it on `main`, the agent runs `roundtable-critique` on the branch diff and records it → the integration-merge gate confirms a fresh record for the tip and allows the merge.

**Verify / standalone.** The maintainer runs the helper on demand against a diff or any target; findings are recorded but nothing is gated.

## What this deliberately does not do

- It does not make a panel verdict a hard pass/fail. Nondeterministic opinion never blocks; only a missing or stale review blocks.
- It does not touch any shipped skill, agent, or plugin hook. Zero distribution surface.
- It does not gate verify or standalone. Those have no commit to hang an edict on and stay advisory by design.
- It does not add a runtime dependency to the plugin. The helper and hook are stdlib-only; roundtable is the maintainer's own MCP environment.

## Testing

- `run_review.py --self-test`: key derivation for binder vs branch, staleness detection (edited binder / advanced tip invalidates), empty-panel rejection, `--check` exit codes.
- `roundtable_gate.py --self-test`: binder-commit detection (staged vs not), merge detection (integration-onto-default vs unrelated merge), fresh-record allow, missing/stale block with a reason naming the fix and the escape, `KARTA_SKIP_ROUNDTABLE` skip, fail-open on internal error.
- `validate_plugin.py` stays green (the new scripts self-test under it; nothing in the plugin manifest changes).

## Open questions

1. Binder content hash — raw file bytes, or a normalized form (so cosmetic whitespace doesn't force a re-review)? Default: raw bytes, simplest and strictest.
2. Should the merge gate also fire on a fast-forward `git merge --ff-only`, or only on merges that create a commit? Default: both — any path that makes the integration tip reachable from the default branch.
3. Record retention — keep every historical record under `.karta/roundtable/`, or only the latest per target? Default: append-only history (the audit trail is the point), matching the bench's honesty doctrine.
