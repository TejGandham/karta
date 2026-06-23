# What's-next visibility — design (V1)

> **Status: settled V1 design.** This is the "what's next" session the multi-binder sequences
> spec ([2026-06-22-multi-binder-sequences-design.md](2026-06-22-multi-binder-sequences-design.md))
> deferred. It introduces the cross-binder `after` edge that spec held back, on the principled
> ground that this is the session chartered to add the DAG. **Order is still never stored** — only
> the dependency edge is. See *Relationship to the multi-binder spec* below.

## Goal

Always show, correctly, **where you are and the single next thing to do** — at both the binder
level (which binder to run next) and the work-item level (which items are ready right now) —
derived fresh from git every time, never stored. Make the moment feel good: one clear next
action, and a live view that lights up as a delivery builds.

## Founding constraints (the DAG charter)

These were set when this work was deferred. Every decision below answers to them:

1. **Order is derived advice, never stored.** The sequence (`new → edit → delete`) is a topo sort
   *computed on demand* from stored edges. It is never written to disk.
2. **Any deviation recomputes the DAG.** Every render recomputes from current git facts and the
   current edges. There is no cached order to drift.
3. **Deviation triggers are few, vetted, and deterministic.** The only triggers are git facts — a
   ref written, a branch merged, a binder added or removed. No heuristic or continuous re-analysis.

The one thing that *is* stored is the dependency **edge** (`after`), exactly as the intra-binder
`depends_on` edge is already stored. A stored edge can dangle, but it can never *silently* mislead:
every render re-resolves it and **surfaces** a dangling or cyclic edge rather than trusting it.

## The decisions (from the brainstorm)

Firm; the rest of the spec follows from them.

1. **One engine, three surfaces.** A single zero-dependency Python script derives one structured
   state from `.karta/binders/*.json` + git. Three thin renderers consume it: a `karta-status`
   command, run footers, and a poll-server status page. They render the same recompute, so they
   cannot disagree, and nothing is cached.
2. **Store the edge, derive the order.** A binder gains one optional top-level field, `after`
   (array of slugs, default empty) — symmetric to a work item's `depends_on`. The suggested order
   is a topo sort over those edges, computed per render, never persisted.
3. **Lightweight poll server, render-on-request.** The status page is served by a zero-dependency
   Python `http.server` that recomputes the state on every request. No WebSocket, no stored page.
   A small same-origin poll keeps it live without a full-page reload.
4. **karta's own visual identity.** The page wears karta's brand — the mascot, the `icon.png`
   favicon, the route-to-a-star motif, karta's palette. Earned and informational in tone, with
   genuinely good UX. No third-party theme.
5. **Still fully manual; no magic.** Nothing auto-runs. The page and the command *advise* the next
   step; the human chooses to take it. No auto-sequencer.

Guiding principle for every open detail: **simple over complete**, and **surface, never silently
degrade**.

## Architecture

### One engine, three surfaces

```
.karta/binders/*.json  +  git refs/branches
            │
            ▼
     karta-status engine          (one zero-dep Python script; recompute, never store)
            │  emits one JSON state
   ┌────────┼─────────────────────┐
   ▼        ▼                     ▼
 command   run footers        poll server  →  status page (HTML, karta-branded)
 (spine)   (deliver/build)        (--watch)
```

### The engine: derivation rules

The engine is read-only. Given the binders directory and git, it derives:

**Binder status** (each binder, from durable git facts that survive an integration branch being
deleted post-merge):

- `merged` — every work item's `done` ref exists and its commit is an ancestor of the default
  branch (`git merge-base --is-ancestor`).
- `in_flight` — the integration branch `karta/<slug>/integration` exists, or some but not all item
  `done` refs are ancestors of the default branch.
- `not_started` — no integration branch and no `done`/`built` refs for the binder.

**Suggested order** — a topo sort over the `after` edges across all binders in `.karta/binders/`.
The result is *derived output*, never written back. If the graph has a cycle, order is `null` and
the engine emits an error (a cycle is unrunnable).

**Next binder** — the `not_started` binder(s) whose `after` predecessors are all `merged`. When
several qualify, the engine picks one deterministically (topo order, then slug order) for the
single next action, while the board still shows them all.

**Work-item frontier** (for each `in_flight` binder) — the same derivation `karta-deliver` already
does, surfaced instead of discarded:

- `done` — `refs/karta/<slug>/item-<id>/done` exists.
- `built` — `built` ref exists, no `done` yet (committed, awaiting the orchestrator's merge).
- `failed` — `failed` ref exists (halted at a gate).
- `building` — the item branch `karta/<slug>/item-<id>` exists with no `built`/`done`/`failed` ref
  (a worker is mid-flight). A soft, live signal; absent that branch the item is not "building."
- `ready` — all `depends_on` are `done`, and the item has no branch/ref yet.
- `blocked` — some `depends_on` is not yet `done`; the engine names the blockers.

**The single next action** — the engine resolves one command to surface, in priority order:

1. A `failed` item in an `in_flight` binder → re-plan or rerun that item (name it).
2. An `in_flight` binder with `ready` items → `karta-deliver <slug>` (resumes the wave loop).
3. No `in_flight` binder but a `next` binder exists → `karta-deliver <next-slug>`.
4. All binders `merged` → done; show the completion line.
5. Frontier empty with items unbuilt (a `blocked`/cycle bottleneck) → surface the bottleneck.

**Warnings and errors** (the "surface, don't degrade" channel):

- Dangling `after` (predecessor slug not present) → **warning**; order is recomputed over the
  binders that do exist.
- Cross-binder cycle → **error**; no order is claimed.
- Empty binders directory → a friendly empty state, not an error.

### The state contract

One JSON object, the sole interface between the engine and every renderer. Representative shape:

```json
{
  "repo": { "default_branch": "main" },
  "order": ["note-tags-new", "note-tags-edit", "note-tags-delete"],
  "binders": [
    { "slug": "note-tags-new",  "after": [],                  "status": "merged",
      "items": { "total": 4, "done": 4 } },
    { "slug": "note-tags-edit", "after": ["note-tags-new"],   "status": "in_flight",
      "is_next": false,
      "items": { "total": 6, "done": 3, "building": 1, "ready": 1, "blocked": 1,
        "detail": [
          { "id": "api-wire", "status": "done" },
          { "id": "tests",    "status": "done" },
          { "id": "cache",    "status": "building" },
          { "id": "docs",     "status": "ready" }
        ] } },
    { "slug": "note-tags-delete", "after": ["note-tags-edit"], "status": "not_started",
      "is_next": false, "items": { "total": 2, "done": 0 } }
  ],
  "next_action": {
    "level": "item",
    "command": "karta-deliver note-tags-edit",
    "human": "resume wave 2 of note-tags-edit — cache is building, docs is ready"
  },
  "warnings": [],
  "errors": []
}
```

`order` is present in the payload but is computed each call — it is the derivation's *output*, not
a stored field read back from anywhere.

### Surface 1 — the `karta-status` command (the spine)

A new read-only skill, `karta-status`. Invoked with no run in flight, it is the only surface that
can answer binder-level "what's next" (a binder merge happens in plain git, when no karta skill is
running). It prints the terminal map:

```
karta · auth-refactor
  ●━━━●─ ─ ○ ─ ─ ─ ─ ☆          new ✓   edit ● now   delete ○

edit  (current binder)            5/6 done
  wave 1 ✓   api-wire ✓   tests ✓
  wave 2 ●   cache building…      docs ready
  ───────────────────────────────────────────
▶ next:  karta-deliver edit       (resumes wave 2)
```

A `--watch <slug>` verb starts the poll server instead of printing once (below). Trigger phrases
include "what's next", "karta status", "where am I".

### Surface 2 — run footers (the in-flow nudge)

`karta-deliver` and `karta-build` call the same engine and print a condensed footer at the tail of
a run (and at each wave boundary in deliver). It is the push counterpart to the command's pull:

```
✓ wave 2 complete — 3 merged, tree green
  edit 5/6 · 1 left   ▶ docs is ready — re-run to finish this binder
```

The footer never blocks and never invents state; it is the engine's `next_action.human` plus the
wave result.

### Surface 3 — the poll server and the status page

`karta-status --watch <slug>` starts a zero-dependency Python `http.server` (the same toolchain as
`validate_binder.py` — nothing to install, ships clean to Claude Code and Codex):

- `GET /state.json` → the engine output, recomputed on every request.
- `GET /` → a static, self-contained HTML shell (embedded CSS, one small inline poller) that
  fetches `/state.json` every ~2s and patches the DOM in place.

It binds `127.0.0.1` on an ephemeral port; on a remote host you forward the port. It prints the URL
and best-effort opens a browser locally (`xdg-open`/`open`), never assuming a display. An optional
`?key=<token>` guards a shared host. There is no WebSocket, no file-watching, no stored page — the
git refs are the source of truth and the engine reads them per request. During a `karta-deliver`
run the page lights green wave by wave; the binder's last merge fires the completion line.

## The `after` cross-binder edge

### Schema

`binder-schema.json` gains one optional top-level field:

```json
"after": {
  "type": "array",
  "items": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$" },
  "default": [],
  "description": "slugs of binders that must merge before this one — the cross-binder dependency the suggested order is derived from; the order itself is never stored"
}
```

It is optional and defaults to empty, so every existing single binder stays valid unchanged. It is
symmetric to a work item's `depends_on`: stored dependency in, derived order out.

### Validation

`validate_binder.py` gains a cross-binder pass that runs **only when other binders are present** in
`.karta/binders/` (a lone binder is validated exactly as today):

- **Resolve each `after` slug.** A slug with no matching binder file → **warning** ("binder
  `<slug>` has a dangling `after: <ref>` — no such binder"). Not a hard failure: the order is
  recomputed over the binders that exist, and the warning surfaces the staleness deterministically.
- **Acyclicity.** A cycle across `after` edges → **error** (exit non-zero). A cycle has no valid
  order and cannot run.

This keeps the per-binder validation untouched for the common case and adds the cross-binder check
only where a sequence exists. Self-tests cover: a clean chain, a dangling `after` (warning), a
two-binder cycle (error), and a single binder with no `after` (unchanged pass).

### `karta-plan` emits the edge

When `karta-plan` emits an ordered set (it already does this since 1.3.0), it now also populates
each binder's `after` with its predecessor(s) — `edit` after `new`, `delete` after `edit`. The
plan-time order advice it speaks once is unchanged in spirit, but is now the same topo sort the
engine derives, so the spoken advice and the live view always agree. The example-sequence binders
(`note-tags-{new,edit,delete}.json`) gain their `after` edges as the worked reference.

## Data flow

```
git refs + binders   →   engine (recompute)   →   one JSON state   →   { command | footer | page }
```

Every arrow is recompute-only. Nothing on the right writes anything on the left. The order, the
frontier, and the next action are outputs of the recompute, never inputs read from storage.

## UX principles for the status page

The page must be *good*, not just correct. The bar:

- **Bottom line, top of page.** The single next action is the hero — set in an amber "marker" band
  echoing karta's diagram titles, with a copy button. A glance answers "what do I do now?"
- **The route is the spine.** Binders render as nodes on a path to a star (the mascot's motif):
  filled green = merged, pulsing amber = in-flight, hollow = not-started. The star is the final
  merge to the default branch. The visual *is* the progress.
- **Status by icon and shape, not color alone.** Every state carries a glyph and label as well as
  a hue, so it reads for color-blind users and in grayscale.
- **Live without flashing.** A ~30-line same-origin fetch poll swaps content in place every ~2s;
  scroll position is kept and a card going green animates. This is the UX upgrade over a bare
  `<meta refresh>`, while staying within the chosen poll architecture (no WebSocket).
- **Legible across the room.** This is a "watch it build" dashboard: generous type and spacing,
  readable from a few feet away.
- **Warm light and a true dark.** Light mode is karta's cream canvas; dark mode uses the mascot's
  navy depth with cream ink, via `prefers-color-scheme`. Both ship in the one embedded stylesheet.
- **Graceful connection loss.** If a poll fails, a subtle "reconnecting" pill appears (no hard
  break, no blank page); it clears on the next good poll.
- **Read-only, zero external dependencies.** No inputs, no forms, no click capture — it reports.
  Vanilla HTML/CSS/JS, no framework, no CDN; the server is Python stdlib only.

### karta visual artifacts used

All from `docs/images/` — karta's own brand, nothing third-party:

- **Mascot** (`mascot.png`) — header lockup; its route-with-nodes-to-a-star is the page's
  organizing metaphor for the binder sequence.
- **Icon** (`icon.png`) — the favicon and small header glyph.
- **Palette**, sampled from the mascot and the existing diagrams, as the page's design tokens:
  warm cream canvas, slate-brown ink, amber/gold route and highlight, route-node green for done,
  soft blue for depth/in-flight, coral for a halt, gold star for the destination.
- **Illustration tone** — the soft, rounded, hand-drawn feel of the diagrams, so the page looks
  like part of karta, not a generic dashboard.

### Tone

Earned and informational. The completion beat states a true milestone — "binder complete — 6/6
merged, tree green, ready to merge to the default branch" — rather than decorative confetti. The
delight is in always knowing the next move and watching the route fill in, not in noise.

## Error handling and edge cases

- **Nothing to show.** No binders, or a binder with no integration branch and no refs → a friendly
  empty/not-started state, never an error.
- **Dangling `after`.** Surfaced as a warning on every surface; the order is recomputed over the
  binders that exist. Bad information is caught, never silently trusted.
- **Cycle in `after`.** Surfaced as an error; no order is claimed; the board still shows each
  binder's status.
- **Integration branch deleted after merge.** Binder status is derived from the persistent `done`
  refs' ancestry of the default branch, so a merged binder still reads `merged` after cleanup.
- **Out-of-order run.** Allowed (karta is manual). Running `edit` before `new` merges shows `edit`
  as in-flight with failing/blocked items; the next-action logic surfaces the real bottleneck. The
  page never pre-empts the human.
- **Server already running / port busy.** Bind an ephemeral port; print the actual URL. A second
  `--watch` is a new server; the user closes the old tab. No shared lifecycle to corrupt.
- **Remote host, no display.** Auto-open is best-effort; the printed URL plus a forwarded port is
  the supported path. The server never assumes a browser is reachable.

## Testing

- **Engine derivation** — unit self-tests over fixture binders + simulated refs: binder status
  (merged/in-flight/not-started), the topo-sorted order, next-action selection across the priority
  ladder, the item frontier (done/built/failed/building/ready/blocked), and the warning/error
  channel (dangling edge, cycle, empty).
- **Validator cross-binder pass** — self-tests: clean chain passes; dangling `after` warns and
  still passes; cycle errors; lone binder unchanged.
- **Server** — `/state.json` matches the engine output for a fixture; `/` returns a self-contained
  document (no external fetches); a token-guarded request without the key is refused.
- **Surface parity** — the command, the footer, and the page derive from the same engine call, so
  one engine test fixture asserts all three render the same next action.
- **The worked example** — the `note-tags` sequence (now carrying `after`) validates standalone and
  produces the expected order and next action.

## Affected files

- `skills/karta-status/` — **new skill**: `SKILL.md` (the command + the `--watch` server verb),
  `scripts/` for the engine, the server, and the status-page assets.
- `skills/karta-plan/SKILL.md` — emit `after` edges when emitting an ordered set; note the order
  advice is now the derived topo sort.
- `skills/karta-plan/references/binder-schema.json` + `scripts/validate_binder.py` — the optional
  `after` field; the cross-binder resolve + acyclicity pass; self-tests.
- `skills/karta-plan/references/example-sequence/note-tags-{new,edit,delete}.json` — add the
  `after` edges.
- `skills/karta-plan/references/binder-reference.md` — document `after` and the derived order.
- `skills/karta-deliver/SKILL.md` and `skills/karta-build/SKILL.md` — emit the engine footer.
- `README.md` and the how-it-works docs — introduce the status surface and the live page.
- Generated mirrors (`.agents/`, `plugins/karta/`, `.codex/`) regenerate via the sync scripts;
  `.claude-plugin/marketplace.json` and the plugin manifests add the new skill; the four
  pre-commit checks stay green.

## Relationship to the multi-binder spec

The multi-binder sequences spec deliberately stored nothing and named this session as the place to
add the DAG. This spec honors that hand-off:

- It **introduces the `after` edge** that spec held back. That is not a reversal of "order is never
  stored" — the *order* is still derived and never persisted; only the *edge* is stored, exactly as
  `depends_on` already is at the work-item level.
- It keeps that spec's "fully manual, no magic": the edge feeds *advice*, never an auto-sequencer.
- `karta-plan`'s set emission is extended (emit `after`), not redesigned. The pipeline
  (`karta-deliver`/`karta-build`/resume) is unchanged except for adding the read-only footer.

The multi-binder spec's "no `after`-field" line is superseded by this document; a pointer will be
added there on commit.

## Out of scope — deliberately deferred

- **WebSocket / instant push.** The ~2s poll is enough; a hand-rolled WS server is more machinery
  than the delight warrants.
- **Auth beyond an optional token.** No accounts, no sessions.
- **Auto-sequencing.** karta never runs the next binder for you. The edge informs advice only.
- **ETA / burndown prediction and historical analytics.** The page shows the present truth, not
  forecasts.
- **Multi-repo or cross-checkout aggregation.** One repo, one `.karta/`.
- **Karta Watch page variants (backlog).** Two treatments present in the Claude Design source but
  deferred from the first live page: the compact **rail** sequence layout (a horizontal
  progress-bar strip as an alternate to the binder cards) and a **click-to-pause** toggle on the
  live timer. Recorded here so they aren't lost; not scheduled.
