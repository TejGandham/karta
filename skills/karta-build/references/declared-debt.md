# Declared Debt

## Marker syntax

karta uses inline debt markers to declare deferrals during build. A marker takes the form:

```
KARTA-DEFER(<id>): <what is deferred> — <why> — follow-up: <what happens next>
```

Place the marker as a comment in the source at the exact site of the deferral.

## What a deferral records

Each marker states three things:

- **What is deferred** — the specific work skipped right now (a test, an edge case, a stubbed dependency, a TODO implementation).
- **Why** — the reason it is deferred now (out of scope for this item, blocks on another item, known unknowns at build time).
- **Follow-up** — who or what carries it forward *outside* karta: a named owner, an entry in the team's own tracker/issue system, or the condition that unblocks it. **karta has no backlog** — it does not schedule, queue, or revisit the deferral itself; this field records where the work lives once karta hands off.

The marker is a snapshot: it states what *is* deferred and why, not a history of decisions.

## Two uses, two bars

A `KARTA-DEFER` marker arises in two very different situations, held to two different bars:

1. **Inline build-time deferral — the implementer's call.** While implementing, the worker may legitimately skip a test, stub a dependency, or defer an edge case, placing the marker at the site. This is a normal, surfaced engineering decision; the item can still complete, carrying the noted debt.
2. **A *capped acceptance-gate failure* is never cleared by a debt marker.** When the read-only acceptance gate caps out (two attempts, still failing), the item halts to a `failed` ref — letting the implementer place a marker to proceed would be grading its own escape. A `KARTA-DEFER` marker does **not** make the capped assertion pass. The only way to accept an unmet acceptance assertion is to **re-plan it as an explicit oracle `opt_out` (with a reason) via karta-plan** and re-run — a deliberate plan-time decision (the binder is read-only to build), recorded and validated like any opt-out. (See the verification-gate reference.)

The distinction is the guardrail: a worker may *note* debt as it builds, but it may never *escape an acceptance cap* by declaring debt.

## Surfacing

Deferrals do not silently disappear. karta collects every `KARTA-DEFER` marker in the built result and surfaces them at the end of the wave — in the build summary and in the item's record. **An item carrying inline debt is never presented as complete without its deferral list shown alongside.** The run's review output includes a consolidated debt register across all items. That register is a **one-time report handed to the user, not a tracked backlog**: karta does not persist, schedule, or revisit it. Carrying the debt forward is the user's job — karta's contribution ends at surfacing it loudly.
