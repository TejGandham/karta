---
name: karta-status
model: haiku
description: >-
  Show what's next in a karta run — where you are and the single next action, at binder and work-item level, derived fresh from git every time and never stored. Read-only. When someone wants to SEE or watch status, it opens the live Karta Watch browser page by default; a one-shot terminal map is the headless fallback. Trigger phrases: "what's next", "karta status", "where am I in this binder", "show me the karta status", "karta watch", "karta-status".
---

karta-status answers one question: **what do I do next?** It reads every binder in
`.karta/binders/` and the karta git refs, recomputes the state, and surfaces a "you are here" view
with one copy-pasteable next action — **by default the live Karta Watch browser page**, or a
one-shot terminal map when there's no browser. It writes nothing and changes nothing.

## How it derives state

All state is git-native and recomputed on every call — there is no stored cursor:

- **Binder order** is a topo sort over the optional cross-binder `after` edge (see
  [karta-plan's binder reference](../karta-plan/references/binder-reference.md)). The order is
  *derived*, never written anywhere. A dangling `after` is surfaced as a warning; a cycle is an
  error. An `after` naming a **delivered** binder — one karta-deliver archived to
  `.karta/binders/archive/` — resolves as satisfied, not dangling.
- **Archived binders** (`.karta/binders/archive/`) are delivered history: the terminal map and
  the session-start summary never list them; the Karta Watch page shows them under its Delivered
  phase.
- **Binder status** — `merged` (every item's `done` ref is an ancestor of the default branch),
  `in_flight` (integration branch exists, or some items merged), or `not_started`.
- **Work-item frontier** (for the in-flight binder) — `done` / `built` / `failed` / `building` /
  `ready` / `blocked`, from `depends_on` and the `refs/karta/<slug>/item-<id>/*` refs.

## Use — open the live page by default

When someone asks for karta status, "what's next", or to **see / watch / show / look at** where
they are, **start Karta Watch, the live browser page.** That is the point of this skill, so it is
the default — not an extra someone has to ask for:

  `uv run --script skills/karta-status/scripts/serve_status.py --root <repo> --port 8765`

It is a **long-running** server (it re-derives state from git on every poll), so start it as a
**persistent/managed process** — a bare `&` or `nohup` is often reaped by the agent runtime before
it binds, so use the runtime's managed background-session mechanism — then **confirm it is serving
and hand the user the working URL**, not just the launch command: `http://127.0.0.1:8765/` (forward
the port on a remote host). The page shows the binder sequence as a card column ending at the
`★ main` integration star, the current binder's work items grouped by state (each with its oracle
and a click-to-expand assertion + command), and the next action as a copy banner; it polls
`/state.json` to stay live. `?theme=light|dark` forces a theme; `--key <token>` gates it behind
`?key=`. It is **self-contained** (vendored Vue, system fonts, no CDN, no build step) and
**zero-dependency** stdlib Python; `serve_status.py --self-test` checks its invariants.

## One-shot text — when there's no browser

When the caller wants a quick textual answer, or there is no browser (CI, headless, a script), run
the engine directly instead of the page:

- `uv run --script skills/karta-status/scripts/karta_next.py` — the route + frontier + `▶ next`.
- `uv run --script skills/karta-status/scripts/karta_next.py --json` — the full state (the page consumes this).
- `uv run --script skills/karta-status/scripts/karta_next.py --footer --binder <slug>` — the one-line run-end nudge.

This skill is read-only and stack-agnostic. It never starts a build, never merges, never writes a
binder. It only tells you where you are and what is next.
