---
name: karta-status
description: >-
  Show what's next in a karta run — where you are and the single next action — at both binder and work-item level, derived fresh from git every time and never stored. Read-only. Trigger phrases: "what's next", "karta status", "where am I in this binder", "karta-status".
---

karta-status answers one question: **what do I do next?** It reads every binder in
`.karta/binders/` and the karta git refs, recomputes the state, and prints a "you are here" map
with one copy-pasteable next action. It writes nothing and changes nothing.

## How it derives state

All state is git-native and recomputed on every call — there is no stored cursor:

- **Binder order** is a topo sort over the optional cross-binder `after` edge (see
  [karta-plan's binder reference](../karta-plan/references/binder-reference.md)). The order is
  *derived*, never written anywhere. A dangling `after` is surfaced as a warning; a cycle is an
  error.
- **Binder status** — `merged` (every item's `done` ref is an ancestor of the default branch),
  `in_flight` (integration branch exists, or some items merged), or `not_started`.
- **Work-item frontier** (for the in-flight binder) — `done` / `built` / `failed` / `building` /
  `ready` / `blocked`, from `depends_on` and the `refs/karta/<slug>/item-<id>/*` refs.

## Use

- **The map.** Run the engine and show its output:

  `uv run --script skills/karta-status/scripts/karta_next.py`

  It prints the route across binders, the current binder's item frontier, and `▶ next: <command>`.

- **As JSON.** `--json` emits the full state — the live page (below) consumes this.

- **The footer.** `--footer --binder <slug>` prints the one-line nudge that `karta-deliver` and
  `karta-build` show at the tail of a run.

## Watch — the live page

For a glanceable, always-fresh view, serve **Karta Watch** — a read-only browser mirror of git
that re-derives the same state on every poll:

  `uv run --script skills/karta-status/scripts/serve_status.py --root <repo> --port 8765`

Then open `http://127.0.0.1:8765/` (forward the port on a remote host). It shows the binder
sequence as a card column ending at the `★ main` integration star, the current binder's work items
grouped by state — each with its oracle and a click-to-expand assertion + command — and the single
next action as a copy-pasteable banner. The page polls `/state.json` to stay live; `?theme=light`
or `?theme=dark` forces a theme; `--key <token>` gates it behind `?key=`. It is **self-contained**
(a vendored Vue, system fonts, no CDN, no build step) and **zero-dependency** stdlib Python.
`serve_status.py --self-test` checks the page's invariants.

This skill is read-only and stack-agnostic. It never starts a build, never merges, never writes a
binder. It only tells you where you are and what is next.
