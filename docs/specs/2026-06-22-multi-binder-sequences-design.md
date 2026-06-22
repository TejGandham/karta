# Multi-binder sequences — design (V1)

> **Status: settled V1 design.** Supersedes the problem brief
> [2026-06-21-multi-binder-planning-discussion.md](2026-06-21-multi-binder-planning-discussion.md),
> which framed the problem and the directions. This spec records the decisions made in the
> brainstorm and scopes V1 deliberately small.

## Goal

Let `karta-plan` emit an **ordered set of self-sufficient binders** when a job naturally
separates into stages that must land in order, and state the suggested order **once, at plan
time, as advice.** karta **persists nothing** about the order and adds **no** cross-binder
machinery. The human runs the binders manually, one at a time.

## The decisions (from the brainstorm)

These are firm, and the rest of the spec follows from them:

1. **Each binder is self-sufficient and independently mergeable.** A sequence is sliced
   expand → migrate → contract (e.g. *new* adds standalone code, *edit* rewires call sites,
   *delete* removes the now-dead old code) so **every binder leaves the default branch green
   on its own.** This is the only model consistent with reviewing and merging each binder to
   main, and karta's existing floor already enforces the compile/type-check/lint half of it.

2. **Order is derived advice, never stored authority.** karta does not persist the order in
   *any* form — no manifest file, no ordering baked into slugs, no `after` field on the binder.
   Any stored order is a second copy of the truth, and a second copy rots the moment the set
   changes: insert a binder and a manifest dangles or a slug number lies. The only order that
   can't go stale is one nothing stores — so V1 simply doesn't store it. The order exists only
   as a plan-time suggestion (below), recomputed from intent whenever it is asked for, never
   read back from a place that could contradict the binders that actually exist.

3. **No magic; fully manual.** No preflight guard, no auto-sequencer, no dependency resolution.
   The human runs `karta-deliver` per binder, in the suggested order, reviewing and merging each
   before *choosing* to start the next.

4. **The only enforcement is the existing floor + gates.** A binder that cannot stand on its
   own cannot clear its own gate and so cannot merge — no new machinery is needed to guarantee
   the green-tree discipline.

Guiding principle for every open detail: **simple over complete.** Cut features or make them
manual before adding dependency-resolution complexity.

## Architecture

The change is almost entirely in `karta-plan`. One new behavior (emit a set), one transient
output (the order advice), one dropped limitation. Nothing is persisted and nothing else in the
pipeline changes.

### 1. `karta-plan` emits a set of binders (when warranted)

`karta-plan` splits a job into a sequence only when **either**:
- the user explicitly asks for separate, ordered binders (the trigger case: *"new first, then
  edit, then delete — separate binders"*), **or**
- the work genuinely requires ordered, separately-mergeable stages — the expand → migrate →
  contract shape is the canonical one.

Default stays **one binder.** A sequence is the exception, not the reflex; do not split work
that fits one binder. When it does split, each emitted binder is a normal binder that passes
`validate_binder.py` on its own and is mergeable on its own.

**Slugs are descriptive and unique — they carry no order.** A set shares a common base prefix
so it reads as a group: `note-tags-new`, `note-tags-edit`, `note-tags-delete`. The prefix groups
them; nothing in the name encodes sequence position (a number would be a stored order that rots
when the set changes). The only hard requirement is the one karta already enforces: slugs are
unique per repo, because the slug is the binder filename and names the integration branch.

**Validate-each, commit-together.** Before presenting the set, `karta-plan` validates **every**
binder in it — each must pass `validate_binder.py` on its own (the existing per-binder check; no
sequence-level validation is added). The whole set is then committed together on the explicit
`commit` verb, exactly as a single binder is committed today. A set that contains an invalid
binder is not presented for commit.

### 2. The order is transient plan-time advice

After drafting the set, `karta-plan` states the suggested order in plain language in its normal
output, once:

> Planned 3 binders. Suggested order: **first** `note-tags-new`, **next** `note-tags-edit`,
> **then** `note-tags-delete`. Review and merge each before starting the next.

This is **advice, not a record.** It is a linear first → next → then suggestion with no graph
and no conditional ordering. It is **not written to disk** — there is no artifact to fall out of
sync with the binders. If the human needs the order again later, that is the job of the deferred
*what's-next* work (see Out of scope), which derives it fresh rather than reading a stored copy.

### 3. Drop the one-binder-per-run limitation

Remove the "not supported in V1" language so karta stops telling the user multi-binder is
impossible while its own vocabulary invites it:
- `skills/karta-plan/SKILL.md:21-25` — the "Scope limits (V1)" line that says it "plans one
  binder per run."
- `skills/karta-plan/SKILL.md:244` — "**One binder per run in V1.** … Multi-binder
  partitioning is not supported in V1."

Replace with language describing set emission and the plan-time order advice.

### Everything else is unchanged

`karta-deliver`, `karta-build`, `karta-verify`, `karta-validate`, `karta-doc-gardner`, resume,
and `validate_binder.py` are **untouched**. Each binder is an ordinary binder; the pipeline sees
one binder at a time, exactly as today. This is stated explicitly so the implementation does not
"improve" these surfaces.

## Data flow — the human's workflow

```
karta-plan  ──▶  N self-sufficient binders   +   plan-time order advice (spoken once, not stored)
                      │
   you ──▶ karta-deliver <new>     ─▶ build/gate ─▶ integration branch ─▶ YOU review + merge to main
   you ──▶ karta-deliver <edit>    ─▶ build/gate ─▶ integration branch ─▶ YOU review + merge to main
   you ──▶ karta-deliver <delete>  ─▶ build/gate ─▶ integration branch ─▶ YOU review + merge to main
```

The human is the sequencer. karta supplies the parts and a one-time suggested order; the human
decides when each stage runs.

## Error handling and edge cases

Because nothing is persisted and there is no cross-binder state, the hard cases stay simple:

- **Nothing drifts.** There is no stored order, so there is nothing to go stale — the design's
  direct answer to "bad information is worse than none."
- **A binder halts at its gate mid-sequence.** Since every earlier binder was self-sufficient
  and already merged green, the default branch is still green. The human fixes or re-plans the
  halted binder and continues. There is no partial-sequence state to unwind.
- **Re-planning one binder.** Binders are independent — re-planning one does not invalidate the
  others (there is no `after` reference or stored order to break). Nothing else needs updating.
- **Single-item binder in a sequence.** It runs through `karta-build`'s single-item path and
  self-merges, like any single-item binder. There is no guard for it to bypass, because there is
  no guard.
- **The human runs binders out of order.** Allowed. If they start *edit* before *new* is
  merged, *edit*'s own floor/gates fail (it references code that is not there yet), surfacing
  the problem the normal way. karta does not pre-empt this — the floor catches it.

## Testing

The change is mostly `karta-plan` prose, so testing is correspondingly light:

- **Each emitted binder validates standalone.** Every binder in a sequence must pass
  `uv run --script skills/karta-plan/scripts/validate_binder.py --binder <each>` independently —
  the existing validator, unchanged, is the check.
- **A worked example.** The `note-tags` case lives as a reference: three binders
  (`note-tags-new`, `note-tags-edit`, `note-tags-delete`), each validating on its own, sliced so
  each leaves the tree green. This documents the expand → migrate → contract discipline.
- **No new validator code, no new artifact.** V1 adds no schema, no validation pass, and no
  persisted file, so there is nothing new to test beyond per-binder validity.

## Affected files

- `skills/karta-plan/SKILL.md` — set emission; descriptive-unique slug guidance; the transient
  plan-time order advice; drop the one-binder-per-run language (`:21-25`, `:244`).
- `skills/karta-plan/references/binder-reference.md` — a short note that a binder may be one of
  an ordered set, with the order given as plan-time advice and **not** persisted (binders
  themselves are unchanged).
- `README.md` and `docs/how-to/*` — soften any "one binder" framing.
- Generated mirrors (`.agents/`, `plugins/karta/`) regenerate from the canonical edits via
  `sync_codex_skills.py`; the four pre-commit checks must stay green.

**No** binder-schema change. **No** `validate_binder.py` change. **No** new file under
`.karta/`.

## Out of scope — deliberately deferred

- **Any persisted order** — a sequence manifest, order baked into slugs, or an `after` field.
  All rejected: a stored order is a second copy that rots when the set changes.
- **Cross-binder dependency machinery** — dependency graphs, cycle/topo resolution, a preflight
  guard, an auto-sequencer. Rejected for V1 to avoid accidental dependency-resolution
  complexity.
- **The DAG / "what's next" visibility session.** Durable, always-fresh next-step guidance — at
  both binder and work-item level — is its own design session. Its founding constraints, set in
  this brainstorm: order is **derived advice, never stored**; any **deviation recomputes** the
  DAG; and the **deviation triggers must be few, vetted, and deterministic** (no continuous or
  heuristic re-analysis). V1 deliberately persists nothing, so it neither blocks nor pre-empts
  that work.
