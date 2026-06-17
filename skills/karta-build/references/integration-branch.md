# Integration Branch

Each binder gets a dedicated integration branch `karta/<slug>/integration`, kept in its own worktree. This branch accumulates completed work items in merge order — it is the resume record and the single reviewable assembled result. It also resolves dependency chains: when item C depends on both A and B, C builds off the integration tip that already contains both.

## Wave loop

1. Re-derive the ready **frontier** — items whose `depends_on` are all merged into integration. (`depends_on` is a **scheduling constraint**; cycles are already rejected at binder creation.)
2. Build the wave's items **concurrently**, each in its own worktree off the current integration tip.
3. **Barrier, then serial merge:** each passing item, *before* merging, **re-validates its oracle against the current integration tip** (which may have advanced as wave-mates merged); on conflict/failure it rebuilds (bounded) or halts.
4. **Post-wave integration check:** run the project's build/type-check on the new tip; on failure **revert the wave and halt-with-CTA** (this catches semantic collisions that text-clean merges miss — e.g. item A renames a helper, item B used the old name). Reverting the wave rewinds both the branch and the wave's `done` refs — see Revert-the-wave below.

## Serial merge queue

Completed items enter a FIFO queue by completion time; the orchestrator processes one merge at a time (the "lock" is sequential processing). For each: rebase/merge the item branch onto the current integration tip → on conflict, bounded rebuild against the new tip, else halt → re-run the item oracle on the merged result → merge (ff or no-ff) → tag and write the done ref.

## Merge ownership — two modes

The integration tip has exactly one writer. Which party that is depends on how the build runs. This section is the canonical statement; the build and deliver skills cite it.

| Mode | When | What the worker does | Who writes the integration tip + done ref |
|-|-|-|-|
| Single-item hatch | the build worker is invoked directly on one item, with no wave around it | builds, runs its floor + acceptance + secret scan, then merges its own item into `karta/<slug>/integration` and writes `refs/karta/<slug>/item-<id>/done` | the worker — it is the only party in play |
| Orchestrated wave | karta-deliver dispatched the build worker as part of a wave | builds, runs its floor + acceptance + secret scan, commits its item branch, writes the `built` marker, and stops — it does not merge into integration and does not write done | the orchestrator — it runs the serial merge queue above |

**The mode signal is explicit.** karta-deliver tells the worker it is in wave mode when it dispatches it. A directly-invoked worker defaults to the single-item hatch. The worker never infers its mode from repo state.

**The pass signal is durable git state, not an ephemeral report.** A wave worker that clears its floor and acceptance writes a durable marker ref `refs/karta/<slug>/item-<id>/built` pointing at its item-branch tip. A halted item writes no built marker and reports the halt. So a wave worker's terminal state is a committed item branch plus a `built` ref — never a merge commit, never a done ref.

**The orchestrator is the single writer of the integration tip.** It merges only items that carry a `built` marker, in the serial FIFO queue above, and re-validates the item oracle against the moving tip before each merge (deliver's wave loop already does this in its serial-merge step). It never trusts the worker's word — it re-checks against the tip it is about to write. Because merges are serial there is no concurrency at the tip, so the double-merge guard (skip the merge when the done ref already exists) is resume-idempotency, not a race fix.

## Tagging and ref scheme

Item commits carry the `[karta:item-<id>]` marker so resume and integration can trace them — in the subject by default, or as a `Karta-Item: item-<id>` git trailer when a Conventional-Commits type prefix owns the subject. Before a wave merges, tag `karta/<slug>/wave-<N>-base` on the pre-merge tip (the revert anchor). After the post-wave check passes, tag `karta/<slug>/wave-<N>` on the completed tip.

Per-item outcomes:
- `refs/karta/<slug>/item-<id>/built` → committed item-branch tip that cleared its floor + acceptance (a wave worker's pass signal; the orchestrator merges only items carrying this)
- `refs/karta/<slug>/item-<id>/done` → merge commit
- `refs/karta/<slug>/item-<id>/failed` → failing branch tip
- `refs/karta/<slug>/item-<id>/in-progress`

`built` and `done` can resolve to the same commit — that is expected, not redundancy. Both refs exist only in orchestrated-wave mode (the worker writes `built`, the orchestrator writes `done` after merging); the single-item hatch writes only `done`. They record *who advanced the tip*, not two different commits. On a fast-forward wave merge `built` and `done` point at the same SHA; they diverge only on a no-fast-forward or multi-item merge — where `done` is the new merge commit and `built` stays at the pre-merge item tip — and on resume. The two refs answer different questions: `built` = "the worker cleared its floor + acceptance here"; `done` = "the integration tip's single writer merged it here". Both are kept even when they coincide.

Resume reads these refs/tags; no separate state file. **Revert-the-wave returns the wave's items to their unbuilt state — it is more than a branch reset.** The orchestrator (the single tip writer): `git reset --hard karta/<slug>/wave-<N>-base` on the integration branch, deletes both the `refs/karta/<slug>/item-<id>/done` **and** `refs/karta/<slug>/item-<id>/built` refs for every item merged in that wave, and does not write the `wave-<N>` success tag (the post-wave check failed before it). The item branches are left in place as a diagnostic artifact. A resumed run then re-derives the frontier — these items have no `done` ref, so they are **rebuilt** against the rewound tip (not re-merged from the old branch); for a semantic collision the binder or an offending item usually has to change first, per the halt's call to action, or the rebuild re-hits the same clash. Leaving the `done`/`built` refs behind would orphan the reverted commits and make the items falsely read as integrated, breaking resume-idempotency.

## Env-injection contract

The test env binds to the wave (started once, torn down once). An item needing a stateful env gets karta-injected isolation params from the binder's `env_contract.isolation_params` (e.g. `PORT`, `COMPOSE_PROJECT_NAME`) **only if `env_contract.supports_isolation` is true**; otherwise the item **serializes** (a "do not parallelise" trigger).

## Honest framing

The model is build-parallel, **merge-serial-with-revalidation** — fast because building dominates wall-clock, not "free."
