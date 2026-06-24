# Humanize binder & work-item presentation — design

**Date:** 2026-06-23
**Status:** approved (design), pending spec review
**Touches:** binder schema · `validate_binder` · karta-plan · karta-status (Karta Watch page) · demo/testbed binder data

## Goal

Make Karta Watch legible to a person trying to understand a run at a glance.
Today the page leads with machine identifiers (`note-tags-editing`,
`backend-update-normalization-coverage`) and hides the human text, so it reads as
mechanical and cryptic. Give every binder and work item a **human-friendly title**
and a **plain-language goal**, authored by karta-plan, and surface those on the page.

## Problem (what's cryptic today)

- A **binder** card's headline is its raw `slug`. The binder has a `motivation`
  field, but the page never shows it, and there is no human title at all.
- A **work item** card's headline is its raw `id`. The item already stores a human
  `title` ("Build compact reusable tag editor component"), but the page demotes it
  to a CSS-truncated subtitle ("Build compact r…").

The information a human needs exists or could exist; the page just leads with the
wrong field. The fix is to author proper human prose into the binder artifact and
have the page lead with it.

## Design decisions (settled)

1. **Authored, not view-time generated.** The friendly prose lives in the binder
   JSON, written by karta-plan. The Karta Watch page stays a self-contained,
   zero-dependency, read-only renderer — it never calls a model or generates prose.
   Deterministic, and consistent with the page's existing charter.
2. **Required and enforced.** Binders are always a karta-generated artifact, never
   hand-written, so the new fields are **required** in the schema and enforced by
   `validate_binder`. karta-plan cannot emit a cryptic binder.
3. **Plain-language at authoring.** karta-plan writes the prose through the bundled
   **karta-plainlanguage** standard (lead with the reader, plain words, active
   voice, no jargon).
4. **Degrade at display, never halt.** The page is read-only. For any binder
   generated before this feature (lacking the fields), it falls back to a
   Title-Cased slug and the `motivation` if present — surfaced, not broken. This
   fallback is a safety net, not the primary path.

## Data model (binder schema)

Two new human fields per level. Machine ids stay as the technical anchor.

### Binder (top level)

| Field | New? | Type | Required | Meaning |
|-------|------|------|----------|---------|
| `slug` | — | string (kebab) | yes | unchanged — names the integration branch and wave tags; shown as a small technical chip |
| `title` | **new** | string, minLength 1 | **yes** | friendly name, e.g. "Tag editing for notes" |
| `summary` | **new** | string, minLength 1 | **yes** | plain-language goal, 1–2 sentences: what this delivers and why it matters |
| `motivation` | — | string | yes | unchanged — the terse internal "why"; distinct from `summary` (which is the reader-facing what) |

### Work item

| Field | New? | Type | Required | Meaning |
|-------|------|------|----------|---------|
| `id` | — | string (kebab) | yes | unchanged — technical anchor; shown as a small chip |
| `title` | — | string, minLength 1 | yes | **promoted to the headline** — friendly short name, e.g. "Wire tag editing into the app shell" |
| `summary` | **new** | string, minLength 1 | **yes** | plain-language goal, one sentence: what this item does |

`additionalProperties` stays `false`; the two `summary` fields and binder `title`
are added explicitly. No other schema fields change.

### Worked example (`note-tags-editing`)

- Binder — title **"Tag editing for notes"**, summary *"Let people add and remove
  tags on a note, and have those tags stick when they reopen it."*
- Item `app-shell-tag-editing` — title **"Wire tag editing into the app shell"**,
  summary *"Hook the tag editor into edit mode so a note's existing tags load and
  changes save."*

## Authoring (karta-plan + karta-plainlanguage)

karta-plan already synthesizes the binder. It gains explicit instructions to:

- author a binder `title` (a friendly name, not the slug) and `summary`;
- author a `summary` for every work item and keep `title` a friendly short name;
- run all four through the **karta-plainlanguage** standard before writing them.

This is skill guidance (prose in `karta-plan/SKILL.md`), not a code path. The
quality bar is the plain-language standard; the validator enforces *presence*.

## Display (Karta Watch) — lead with the human text

The page change is presentation only; the engine and the git derivation are
untouched.

**Binder card.** Headline becomes `title`. The `slug` moves to a small monospace
chip next to it (still visible — it is how you find the branch). A new blurb line
under the header shows `summary`.

**Work-item card.** Headline becomes `title`. The `id` moves to a small monospace
chip. The description line shows `summary` in full (wraps to ~2 lines) instead of
the truncated title. The click-to-expand oracle / assertion / command detail is
unchanged.

```
 BEFORE                                  AFTER
 ┌─────────────────────────────┐         ┌─────────────────────────────┐
 │ ✈ note-tags-editing   100%  │         │ ✈ Tag editing for notes 100%│
 │   ⟨5 runs · 3→1→1⟩          │   →     │   ⟨note-tags-editing⟩ binder │
 │   (no description)          │         │   Let people add and remove │
 │                             │         │   tags on a note, and have… │
 └─────────────────────────────┘         └─────────────────────────────┘
```

**Fallback rules (read-only, never halt):**

- Binder headline: `title` if present, else the slug Title-Cased (`note-tags-editing`
  → "Note Tags Editing").
- Binder blurb: `summary` if present, else `motivation` if present, else omitted.
- Item headline: `title` if present, else `id`.
- Item description: `summary` if present, else `title` if present, else omitted.

The slug/id chip always shows the real identifier regardless of fallback.

## Enforcement (`validate_binder`)

- The schema marks binder `title` + `summary` and item `summary` as required, with
  `minLength: 1`.
- `validate_binder` reports a missing or empty field as an **error** (the existing
  hard-gate path), so a binder without them fails validation.
- Self-test fixtures updated to include the new fields; a negative fixture asserts a
  missing `summary` is rejected.

## Migration / demo

- Backfill the binders behind the current screenshot (the demo repo) and the
  karta-testbed binders (`note-tags-{new,edit,delete}`) with authored titles +
  summaries, so the page reads cleanly immediately.
- Update the `validate_binder` and `serve_status` self-test fixtures.
- No migration tool for arbitrary old binders — they render via the page fallback,
  and any real binder is regenerated by re-planning.

## Out of scope

- View-time prose generation, translation, or summarization on the page.
- Changing the engine, the git derivation, or the phase/wave layout.
- Reflowing the expand detail (oracle/assertion/command) — unchanged.
- The backlogged Karta Watch rail layout + click-to-pause toggle.

## Testing & acceptance

- `serve_status.py --self-test`: assert the page leads with `title`, renders the
  slug/id as a chip, renders `summary`, and that the fallback path produces a
  Title-Cased slug when fields are absent.
- `validate_binder.py --self-test`: assert the new required fields pass on a
  complete binder and fail (with a clear error) when `summary`/`title` is missing.
- The four pre-commit checks stay green; demo + testbed binders validate.
- Visual: the binder and work-item cards lead with human text; the slug/id is a
  secondary chip; no truncated half-sentences.

## Acceptance

A person opening Karta Watch can read, per binder and per work item, a friendly
name and a plain-language goal — without decoding a kebab-case slug — while the
technical id stays one glance away.
