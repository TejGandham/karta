# Doc-garden — design

- Date: 2026-06-18
- Status: approved (brainstorming) — pending implementation plan
- Scope: an opt-in, fully automatic documentation-correction step for karta. When on, doc drift is rewritten to match the code automatically; there is no advisory tier, no human waive, and no halt. Borrowed from keel's doc-gardener, made liberal and auto-correcting.

## 1. Goal and decisive constraints

Documentation rots. karta should be able to keep a repo's prose in lockstep with its code without a human babysitting it. The constraints (all set by the user, the last three decisively):

- **Opt-in, then always required.** Off by default. A durable repo switch turns it on; once on, every delivery runs it and it cannot be silently skipped.
- **Fully automatic correction.** When on, the gardener **rewrites** drifted docs to match the current code and commits the fix. It does not just report.
- **No waive, no hand-raising, no halt.** There is no human-in-the-loop step, no accept/defer, no "block and ask." The delivery is never paused for a doc decision.
- **All or nothing.** No `INFO`/advisory tier and no severity triage. When on, every drift found is fixed; when off, nothing runs.
- **Scope is never static.** What to garden is recomputed every run from the live repo — never a stored doc list or a cached analysis — so files created after opt-in are always in scope.
- **Liberal checks.** General drift (broken pointers, docs that mis-describe changed code, future-tense-now-landed), not keel's strict "no timeline in docs" doctrine.
- **Cross-platform + dual-runtime.** Same generate-and-guard discipline as the rest of karta: one canonical agent, drift-guarded Codex projections, works on Claude Code and Codex, macOS/Linux/Windows.

## 2. How keel does it, and how karta differs

keel's `doc-gardener` is a **read-only** agent: it sweeps a doc surface, writes a findings report, and the *orchestrator* auto-applies the HIGH findings while INFO is left for a human. It runs as a required pipeline step (keel-pipeline Step 9), plus an ad-hoc full-repo mode and an advisory commit-hook nudge.

karta keeps the idea (sweep the doc surface for drift, scoped by the change blast radius, recomputed live) and changes three things to match the constraints above:

- The gardener is a **writer**, not a reporter. It corrects drift directly. (keel: read-only + orchestrator applies.)
- There is **no severity split and no human path**. keel auto-applies HIGH and leaves INFO to a person; karta fixes everything it finds. (All or nothing.)
- It is **opt-in** (off by default), not on-by-default-skip-if-permitted.

## 3. The model

### 3a. Opt-in switch — `.karta/doc-garden.json`

A small, durable file is the *only* static element. Consistent with karta's existing `.karta/binders/<slug>.json` and `.karta/secret-scan-allowlist`.

```json
{ "enabled": true, "focus": "optional freeform note biasing the gardener, e.g. 'keep the public API docs and the architecture overview honest'" }
```

- **Present and `enabled: true`** → opted in. Every `karta-deliver` run executes the doc-garden phase; it cannot be skipped.
- **Absent (or `enabled: false`)** → off. The phase no-ops.
- `focus` is freeform guidance only — it biases the LLM's attention. It is **not** a doc list. No file enumerates which docs to check.

A JSON Schema (`references/doc-garden-schema.json`) gates the file shape, and an example ships.

### 3b. Scope — recomputed every run, never stored

On each run the gardener re-derives its scope from the live repo, so nothing goes stale:

- **Doc surface** — glob the current prose surface (`README*`, `docs/**`, `AGENTS.md`, `CLAUDE.md`, `ARCHITECTURE*`, and other top-level/`docs` markdown). A doc created in an earlier delivery is in the set automatically the next run.
- **Blast radius** — the live `git` diff of this delivery (all files changed across the delivered items versus the binder base). New code files are in it automatically.
- Nothing about scope is persisted or cached; the enumeration *is* the analysis, redone each run. This is the same "re-derive by reading on each run, no stored state" rule karta's other agents follow.

Coverage of the three drift sources: a new **doc** is caught by the fresh glob; new/changed **code** by the live diff; a doc that rots with **no related code change** by the run's cheap repo-wide pass (pointer/existence + future-tense-now-landed across all current docs) and by the standalone full sweep.

### 3c. The `karta-doc-gardener` agent (a writer)

A new agent, canonical at `agents/karta-doc-gardener.md`. Unlike the two read-only gate agents, it **edits docs**. Given the binder, the integration diff range, the live doc surface, and the optional `focus`, it:

1. Re-enumerates the doc surface and the blast radius (3b).
2. Finds drift (liberal): broken path/symbol pointers; prose that no longer matches changed code; future-tense promises for things now landed.
3. **Corrects** each drift in place — rewrites the doc to current state, scoped strictly to the drifted content (it does not restyle or expand beyond the fix).
4. Re-verifies its own output; loops until a clean pass or a small bound (default 3). On the bound, it lands what it corrected and records any residual it could not resolve in its summary — it does **not** halt the delivery or raise a human (no hand-raising).
5. Emits a terse envelope (`corrected_count`, `residual`) for the caller's commit record.

It writes **only** doc-surface files. It never touches code, tests, the binder, or refs.

### 3d. Integration — one spawn site, three entry points

- **`karta-doc-garden` skill** — the sole spawn site for the agent (mirrors how `karta-verify` is the sole spawn site for the gate agents). It resolves the agent adaptively per runtime (registered subagent on Claude / Codex-with-TOML; bundled instructions on a Codex plugin install) and bundles the agent instructions at `references/karta-doc-gardener.agent.md` so it works on a Codex plugin install with no setup.
- **`karta-deliver` terminal phase `deliver:docgarden`** — after the final wave merges into the integration branch, if `.karta/doc-garden.json` is opted in, karta-deliver invokes the `karta-doc-garden` skill over the whole delivery's blast radius, then commits the corrections as a distinct `docs: garden <slug>` commit on the integration branch. If opted out, the phase no-ops with a one-line note.
- **Single-item hatch** — `karta-build` invoked directly applies the same terminal step when opted in.
- **Standalone / ad-hoc** — a user can invoke `karta-doc-garden` directly for a full-repo correction pass, independent of a delivery.

The correction lands as its own labeled commit so a human reviewing the integration branch (karta's normal review-and-merge point) sees exactly what the gardener changed and can revert it like any commit. That is the review surface — there is no inline waive.

### 3e. No human, no halt

The doc-garden phase never blocks the delivery and never asks a person anything. It corrects, commits, and the delivery proceeds. The only record is the `docs: garden` commit and the gardener's envelope folded into the delivery report.

## 4. Cross-platform + Codex compliance (generate-and-guard)

The new agent and skill follow the same discipline just built for Codex:

- Canonical `agents/karta-doc-gardener.md` → generated `.codex/agents/karta-doc-gardener.toml` and the bundled `skills/karta-doc-garden/references/karta-doc-gardener.agent.md`, both via `sync_codex_agents.py`.
- The new `skills/karta-doc-garden/` is mirrored into `.agents/skills/` by `sync_codex_skills.py` and carries its own `agents/openai.yaml`.
- **Sandbox derivation.** `sync_codex_agents.py` sets `sandbox_mode` from the agent's declared tools: an agent whose `tools` include `Write`/`Edit` (the gardener) → `sandbox_mode = "workspace-write"`; otherwise → `read-only` (the two gates). On a Codex plugin-install fallback, `karta-doc-garden` spawns a normal workspace-write worker (not the read-only `explorer`) with the bundled instructions.

## 5. Validator changes — `scripts/validate_plugin.py`

- The `.codex/agents/*.toml` sandbox check becomes per-agent: assert each agent's `sandbox_mode` equals the value derived from its canonical `tools` (read-only for the gates, workspace-write for the gardener) — not a blanket "must be read-only."
- The new agent's two projections are guarded by the existing projection byte-equality check automatically (it iterates all `agents/*.md`).
- The new skill is guarded by the existing mirror parity, openai.yaml, and SKILL-link checks automatically.
- New: if `.karta/doc-garden.json` is committed as the repo's own example/config, validate it against `references/doc-garden-schema.json`. (The schema + example live under the `karta-doc-garden` skill.)

## 6. Docs

- README: a short "Automatic doc-garden (opt-in)" subsection — how to turn it on, what it does, where the corrections land.
- `docs/how-to/doc-garden.md`: enabling it, the `.karta/doc-garden.json` shape, the dynamic-scope guarantee, what gets corrected, and how to review/revert the `docs: garden` commit.
- AGENTS.md: note the new canonical agent + skill and that the gardener is the one *writer* agent.

## 7. Non-goals

No human/waive/halt/accept path. No severity tiers or advisory `INFO`. No keel-style P5 timeline doctrine. No static or cached doc list. No commit hook (the karta-deliver phase is the enforcement). The gardener does not refactor or expand docs beyond correcting drift, and it never edits code, tests, or the binder.

## 8. Risk note (accepted)

An LLM rewriting committed documentation automatically can mis-correct. This is accepted by explicit user direction (fully automatic, all-or-nothing). Mitigations that do not reintroduce a human gate: corrections are scoped strictly to detected drift; they land as a single labeled `docs: garden` commit on the integration branch (never pushed, never on `main`), which is karta's normal human review-and-merge surface; and the gardener re-verifies its own output before committing.

## 9. File inventory

Created:

- `agents/karta-doc-gardener.md` (canonical, writer agent)
- `.codex/agents/karta-doc-gardener.toml` (generated, `workspace-write`)
- `skills/karta-doc-garden/SKILL.md` + `skills/karta-doc-garden/agents/openai.yaml`
- `skills/karta-doc-garden/references/karta-doc-gardener.agent.md` (generated, bundled instructions)
- `skills/karta-doc-garden/references/doc-garden-schema.json` + an example `.karta/doc-garden.json`
- `.agents/skills/karta-doc-garden/…` (generated mirror)
- `docs/how-to/doc-garden.md`

Modified:

- `skills/karta-deliver/SKILL.md` (new terminal phase `deliver:docgarden`, opt-in gated)
- `skills/karta-build/SKILL.md` (single-item-hatch terminal step, opt-in gated)
- `scripts/sync_codex_agents.py` (derive `sandbox_mode` from tools)
- `scripts/validate_plugin.py` (per-agent sandbox expectation; optional `.karta/doc-garden.json` schema check)
- `README.md`, `AGENTS.md`

Unchanged: the two gate agents and their read-only contract; the binder schema; all existing pipeline logic outside the new terminal phase.
