# Delivery Stop-gate — the sixth hook

Date: 2026-07-14. Status: adversarially reviewed (4-model roundtable critique; confirmed findings folded in — `¬failed` predicate clause, committed-archive-only semantics, HEAD-inclusive binder enumeration, plumbing-only ref reads, expected-negative vs fail-open separation, atomic sentinel writes). Closes the "delivery Stop-gate" deferral from the [phase 1 hooks design](2026-07-06-hooks-phase1-design.md).

## Why

A karta delivery's correctness rests on two hand-offs that happen *after* the interesting work is done: the orchestrator must run the serial merge queue over every `built` item, and a complete run must archive its binder (end-of-life, 1.17.0). Both live as skill prose. An orchestrator under context pressure can end its turn having declared victory with `built` refs still standing, or merge everything and skip `deliver:archive` — and today nothing below the agent catches either. The refs were designed to make these states *recoverable*; this hook makes them *not survive the end of a turn unannounced*.

## Verified capability (2026-07-14, binary v2.1.207)

Checked against the installed Claude Code Bun bundle, same method as the writer-confinement `agent_type` verification:

- Plugin `hooks/hooks.json` supports the `Stop` event; payload schema (zod, in-binary) carries `hook_event_name: "Stop"`, `stop_hook_active: boolean`, `last_assistant_message` (optional), plus the base fields (`session_id`, `transcript_path`, `cwd`, …).
- Exit 2 from a Stop hook blocks the stop: stderr is fed to the model, which continues working — a block can carry the exact corrective action.
- The harness has its own loop backstop: repeated Stop-hook blocks are capped (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`) and the turn is force-ended, with in-binary guidance: *"For Stop/SubagentStop hooks, check stop_hook_active in the input and return success while it's true."*
- The Stop payload carries **no** skill/agent context in a main session — a hook cannot know "this is the deliver session" except by repo state. (SubagentStop does carry `agent_id`/`agent_type` — relevant to a future whiff-worker gate, out of scope here.)

## What ships

### 1. `hooks/scripts/guard_delivery_stop.py` — sixth hook, fifth guard

Registered in `hooks/hooks.json` under `Stop` (matcher `*`, timeout 30). Same contract as the other five: payload JSON on stdin, exit 0 allows, exit 2 blocks with a one-paragraph reason on stderr, stdlib-only, `--self-test`. **Fail-open**: any internal error (no git, unreadable binder, missing fields) exits 0 — a Stop trap is strictly worse than a missed nudge. This guard is corrective, not fail-closed.

### 2. Detection — repo state only, live binders only

Resolve the repo root with `git rev-parse --show-toplevel` from the payload `cwd` (a session may sit in a subdirectory), and read all git state through plumbing (`for-each-ref`, `cat-file`, `ls-tree`) — never by inspecting `.git/refs/` files, which go silent once refs are packed. Process only payloads whose `hook_event_name` is `Stop` with no subagent fields; anything else exits 0.

Enumerate **live** binders as the union of `.karta/binders/*.json` in the working tree and in `HEAD` (never `archive/` — a delivered slug's surviving refs are history, not a finding). Including `HEAD` matters: a crash between the archive `git mv` and its commit removes the live file from disk while the archival is not yet real. For each slug, test two conditions:

- **built-unmerged** — some `refs/karta/<slug>/item-<id>/built` ref (enumerated by ref glob, not from `work_items`, so an orphaned ref still counts) has no matching `done` **and no matching `failed`**: the serial merge queue never ran to completion. The `¬failed` clause keeps a merge-time halt that left `built` standing — a parked four-way-choice state — from re-firing the gate.
- **complete-unarchived** — the binder has **at least one** work item (an empty `work_items` is vacuously complete and never a finding), *every* item has `done`, and the archive file `.karta/binders/archive/<slug>.json` is not **committed** anywhere it counts: not in `HEAD`, not on `refs/heads/karta/<slug>/integration`, and not on the default branch (a stale feature-branch checkout must not re-demand an archive that already merged). An archive file merely present on disk or staged but uncommitted does not count — doctrine requires a commit on the integration branch. When the archive commit sits on the integration branch awaiting human review/merge, that is the *correct* end state — no finding.

`git cat-file -e` / missing-branch negatives are **expected results that feed the finding**, not internal errors — the fail-open path is reserved for genuinely unexpected failures (no git binary, unreadable payload), never for "ref not found".

Deliberately **not** conditions:

- A standing `failed` ref — a halted item parked at the four-way human choice is a designed resting state; the session-start injection and `karta_next.py` already surface it.
- A partially-delivered binder with no `built` refs standing (some `done`, rest unbuilt) — "deliver the rest later" is a legitimate stopping point the resume flow owns.
- Anything inferred from `last_assistant_message` prose — text-sniffing is the nondeterminism karta exists to avoid.

### 3. Block-once mechanics

On a finding, the guard blocks **at most once per (session, state)**:

1. If `stop_hook_active` is true → exit 0 (the harness-documented loop guard).
2. Compute a state fingerprint: SHA-256 over the sorted `(slug, condition, item-ids)` tuples.
3. Read the sentinel `<git-common-dir>/karta-stop-gate.json` (per-repo, shared across worktrees). If it maps this `session_id` to this fingerprint → already nudged for exactly this state → exit 0.
4. Otherwise record `session_id → fingerprint` (pruned to 20 sessions, written atomically via temp file + `os.replace`; a lost concurrent write costs at worst one redundant nudge, and the harness cap backstops all of it) and exit 2. The reason names each finding and its fix verbatim:
   - built-unmerged: *"binder `<slug>`: items `<ids>` carry `built` but no `done` — the serial merge queue did not finish. Re-enter karta-deliver's merge step: for each, re-validate its oracle against the current integration tip, merge FIFO, write the `done` ref; or tell the user plainly that the delivery is stopping mid-wave and how to resume."*
   - complete-unarchived: *"binder `<slug>`: all items are `done` but the binder was never archived. Run the end-of-life step (`deliver:archive` / karta-build 9c-single): `git mv` it to `.karta/binders/archive/<slug>.json` and commit on the integration branch."*

A changed state (new fingerprint — e.g. one more item merged, still one stranded) blocks once more; an unchanged state never re-fires in that session. The sentinel is written **only on a block**, which gives clean semantics to a partial fix inside a stop-hook continuation: the second stop attempt allows (per `stop_hook_active`), nothing is recorded, and the next turn's stop re-evaluates the changed state fresh — the nudge is deferred one turn, not lost. The harness block-cap is the final backstop above all of this.

The gate is deliberately a **nudge, not a wall**: after its one block per state, a stop with the same state succeeds. That is doctrine, not a weakness — a stranded `built` ref is exactly the state the refs were designed to make resumable, and the resume flow (deliver preflight, session-start injection, `karta_next.py`) owns recovery across sessions. A gate that hard-blocked until clean would trap a user who legitimately wants to stop and resume later.

### 4. Docs + validation

- `docs/how-to/hooks.md`: one new row in the enforcement table ("A delivery may not end dirty"), and a sentence in the asymmetry section (Codex has no Stop surface; doctrine unchanged there).
- `hooks/hooks.json` `description` mentions the sixth concern.
- `validate_plugin.py` already iterates the manifest — the new script's existence, executability, and `--self-test` are covered with no extension.
- Skill doctrine unchanged: karta-deliver/karta-build keep stating the merge-queue and archive steps; the hook is belt-and-suspenders below them.

## Self-test coverage (fixture git repos, `--self-test`)

no live binder → allow · archived-only slug with surviving refs → allow · in-flight binder, no `built` standing → allow · built-unmerged → block, reason names slug+items · item with `built` **and** `failed`, no `done` → allow (parked) · empty `work_items` → allow · complete-unarchived (no archive anywhere) → block · complete-unarchived with **no integration branch at all** → block (missing branch is a negative, not an error) · archive `git mv`'d but uncommitted → block · complete with archive committed on integration branch only → allow · complete with archive in `HEAD` → allow · archive merged to default branch, stale feature-branch checkout → allow · two live binders with mixed findings → one block, fingerprint covers both · payload `cwd` in a subdirectory → still detects · SubagentStop-shaped payload → allow · `stop_hook_active` true → allow · same session + same fingerprint → allow on second call · same session + changed fingerprint → block again · new session, same state → block once · malformed binder JSON → allow (fail-open) · non-git cwd → allow · sentinel pruning at 20 sessions.

## Explicitly out of scope

SubagentStop whiff-worker detection (a wave worker ending with neither `built` nor `failed`; feasible — the payload carries `agent_type` — but a separate design), Codex parity (no Stop surface upstream), any gate on `failed` refs, and any session-intent inference from prose.

## Risks accepted

The Stop event fires on every turn of every session in any repo with the plugin enabled; the guard's fast path (no live binders) is one glob plus one `ls-tree` and must stay dependency-free and quick. A session doing unrelated work in a repo with a genuinely stranded delivery gets one nudge — that is the feature, not collateral: the repo state is dirty regardless of who stopped, and transcript-sniffing to guess session intent is the nondeterminism karta avoids. Plugin-hook precedence remains overridable, as documented. The sentinel adds an untracked file under `.git/` — invisible to the working tree by construction.
