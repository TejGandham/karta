# SME domain-expert packs — design

- Date: 2026-06-21
- Status: approved (brainstorming) — pending implementation plan
- Scope: an advisory, auto-applied domain-expertise layer for karta. karta ships curated **SME packs** (knowledge files of stack-specific do's and don'ts), auto-detects which apply from the repo, pins them in the binder at plan time, and feeds them to the synthesis (plan) and implementer (build) so work is decomposed and written to each stack's norms. Ships `angular` and `python-fastapi` built-ins; projects extend with their own. Purely advisory — never a gate.

## 1. Goal and decisive constraints

karta is stack-agnostic by design: it makes no assumption about framework, component library, data layer, or layout, and it reads only the binder and the repo at runtime. That neutrality is a strength for orchestration, but it leaves a gap — karta has no opinion about *how* a given stack should be written. An Angular view and a FastAPI endpoint each have a body of accepted patterns and anti-patterns that a good engineer applies without being asked. This feature gives karta that voice: the right domain expert advises during planning and implementation, automatically.

Constraints (all set by the user):

- **Knowledge packs, not subagents.** An expert is a curated markdown reference loaded inline by the existing plan and build flows — not a separately dispatched advisor session. Cheapest, always-on, and in keeping with karta's "reads at runtime" minimalism.
- **Auto-detected, pinned in the binder.** karta-plan matches packs from the resolved stack/deps and records the chosen pack ids in the binder. karta-build reads that field, so plan and build apply the exact same experts. The binder stays the cross-skill contract.
- **Built-in plus project overlay.** karta ships curated built-ins; a project drops its own packs in `.karta/sme/` to cover arbitrary stacks or override a built-in. Stacks are open-ended, and packs are meant to be fine-tuned over time.
- **Purely advisory — never a gate.** SME guidance shapes how code is written, never whether it passes. The oracle/contract gates are unchanged and SME-unaware. karta keeps exactly one gate authority.
- **Lean V1.** No kill switch (no match → nothing happens, zero cost), no per-item override, no advisor subagent sessions, no versioning or registry beyond the flat directory.
- **Cross-platform, dual-runtime.** Same canonical-vs-generated discipline as the rest of karta: canonical source under `skills/`, drift-guarded Codex projections, works on Claude Code and Codex across macOS/Linux/Windows.

## 2. Relationship to karta's "no registry, stack-agnostic" stance

There is a real tension to name: a curated catalog of stack-specific experts is, in a sense, the registry karta has avoided. The design resolves it on three points:

- **The catalog is not invariant state.** SME packs carry no run state, no per-project configuration, nothing a later stage reads back. They are static reference text — the same category as the `skills/_shared/*.md` material karta already ships. The binder's `sme[]` is a resolved-at-plan fact, exactly like `design_facts.stack`.
- **It does not narrow the orchestration.** karta's pipeline (plan → deliver → build, gated by verify/validate) is untouched. SME is additive context; remove every pack and karta behaves exactly as it does today.
- **Stack-specificity lives only in advisory text, never in control flow.** No skill grows a `case "angular"` branch. The packs are data; the matcher is generic; the consumers (plan synthesis, build implementer) load whatever matched and otherwise run their existing stack-agnostic flow.

## 3. The model

### 3a. An SME pack

A markdown knowledge file. Frontmatter declares identity and match tokens; the body is the advisory content. The body sections are a light convention (Do / Don't / Patterns / Review checklist), not a rigid schema — packs are meant to be edited freely.

```
skills/_shared/sme/angular.md
---
name: angular
description: Angular architecture do's and don'ts
match: ["@angular/core", "angular", "@angular/cli"]
---
## Do
- Standalone components; signals for local state; `inject()` over constructor DI.
- OnPush change detection; `takeUntilDestroyed` for subscription cleanup.
## Don't
- No logic in templates; no `any`; no manual `.subscribe()` without teardown.
## Patterns
- Smart/dumb component split; typed reactive forms; route-level lazy loading.
## Review checklist
- [ ] Change-detection strategy set
- [ ] No leaked subscriptions
- [ ] Inputs/outputs typed
```

- `name` — the pack id (kebab-case, unique). This is what lands in the binder's `sme[]` and what a project-local file overrides by reusing.
- `description` — one line, shown in the plan report.
- `match` — an array of tokens compared against the repo's detected dependencies and stack phrase (see 3c). A token matches if it appears as a dependency name (e.g. `@angular/core` in a manifest) or as a substring of the resolved stack phrase (e.g. `angular`, `fastapi`).

### 3b. Where packs live

- **Built-in (canonical):** `skills/_shared/sme/*.md`. Per karta's `_shared` convention, each consumed file is copied byte-equal into the consuming skills' `references/` trees: `skills/karta-plan/references/sme/` and `skills/karta-build/references/sme/`. The Codex mirror under `.agents/skills/` and the marketplace projection under `plugins/karta/` are regenerated by `sync_codex_skills.py`. V1 ships two: `angular`, `python-fastapi`.
- **Project-local overlay:** `.karta/sme/*.md` in the user's repo. A new `name` adds an expert for an unsupported stack; a reused `name` overrides the built-in of that name. This is the open-ended, fine-tune-as-you-go surface and needs no plugin change. It sits beside the existing `.karta/binders/` directory.

**Resolution order is project-local first, then built-in**, keyed by `name`. A `.karta/sme/angular.md` fully replaces the built-in `angular` for that repo.

### 3c. Matching — auto-detect at plan, pin in the binder

karta-plan's survey (`plan:survey`) already resolves the stack phrase and reads dependency manifests. A small, generic matcher runs after the survey:

1. Enumerate available packs (project-local overlaid on built-in, by `name`).
2. For each pack, test its `match` tokens against the detected dependency set and the resolved stack phrase.
3. The matched pack ids become the binder field `sme`.

```jsonc
{
  "design_facts": { "stack": "Python/FastAPI + Angular SPA" },
  "sme": ["python-fastapi", "angular"]   // polyglot repo pins both
}
```

`sme` is an optional array of strings at the binder top level. Absent or `[]` means no expert applied — the zero-cost default.

### 3d. Plan integration

After matching, karta-plan loads the matched packs and threads their guidance into Phase 2 (`plan:synthesize`): the synthesis subagent brief gains a **domain-guidance** section carrying the matched packs' do's/don'ts, so decomposition, `contract`s, and `oracle`s reflect each stack's norms (an Angular item's contract speaks in standalone-component terms; a FastAPI item's oracle expects Pydantic-validated shapes). The main thread leans on the same guidance during its review of the draft.

The pinned ids are written into the binder at Phase 5 (`plan:emit`) alongside the other resolved facts. The Phase 6 report (`plan:report`) gains one line: **Experts applied: angular, python-fastapi** (or *none*).

### 3e. Build integration

karta-build reads the pinned `sme[]` during Phase 1 (`build:gate`) as a cached value, resolves each pack (project-local → built-in), and loads it **before Phase 4 (`build:implement`)**. The implementer follows the loaded guidance while writing code and while fixing gate kickbacks. In a polyglot repo, the implementer applies the pack(s) relevant to the area the item targets (the same area resolution build already does for `App dir / target`).

**Resolution is best-effort and never blocks.** A pinned pack that cannot be resolved at build time (e.g. a project-local pack present at plan time but absent on this machine) produces a **non-fatal note in the build report and the run continues**. Advisory guidance is never on the critical path.

### 3f. Safety and gates — explicitly unchanged

- SME guidance is context for the *writer*, never input to a *judge*. `karta-verify`, `karta-acceptance-reviewer`, and `karta-safety-auditor` are unchanged and SME-unaware. There is still exactly one gate authority, judging against the oracle/contract.
- `validate_binder.py` validates `sme` as an optional array of strings (schema only). It does **not** require the named packs to resolve — project-local packs may live on another machine, and requiring resolution would couple the validator to the filesystem overlay. Runtime resolution is build's concern, and a miss only warns.

## 4. Wiring (canonical-vs-generated discipline)

- New canonical content: `skills/_shared/sme/angular.md`, `skills/_shared/sme/python-fastapi.md`.
- Per-consumer copies: `skills/karta-plan/references/sme/*.md` and `skills/karta-build/references/sme/*.md`, kept byte-equal to `_shared` and checked by `check_shared_copies.py`.
- `sync_codex_skills.py` regenerates the `.agents/skills/` mirror and the `plugins/karta/` projection so the new reference dirs travel to Codex; `validate_plugin.py` covers them in its single pass.
- SKILL.md edits: `karta-plan` (matcher step after `plan:survey`, domain-guidance in `plan:synthesize`, `sme` in `plan:emit`, the report line in `plan:report`); `karta-build` (read `sme[]` in `build:gate`, load packs before `build:implement`, missing-pack note in `build:report`).
- `references/binder-reference.md` gains the `sme` field; `validate_binder.py` gains the optional-string-array check.
- `AGENTS.md` layout table gains a row for `skills/_shared/sme/` and the per-skill copies; `README.md` gains a short SME section.

## 5. Non-goals (YAGNI)

- No advisor subagent sessions — packs are inline context only.
- No gate involvement — SME never blocks or judges.
- No kill switch — no match is the off state.
- No per-item `sme[]` override — packs apply by detected stack/area.
- No pack versioning, dependency, or registry beyond the flat `sme/` directory.
- No automated authoring of project-local packs — that is the user's content.

## 6. Build sequence (outline for the plan)

1. Author the two built-in packs and the `_shared` → per-skill copies; wire `check_shared_copies.py`.
2. Add the `sme` field to `binder-reference.md` and the `validate_binder.py` schema check.
3. karta-plan: matcher after `plan:survey`, domain-guidance in synthesis, pin in `plan:emit`, report line.
4. karta-build: read `sme[]`, resolve + load packs before implement, missing-pack note.
5. Regenerate Codex projections (`sync_codex_skills.py`); update `AGENTS.md` and `README.md`.
6. Run the four pre-commit checks (`validate_plugin.py --self-test`, `check_shared_copies.py --self-test`, both `--check` syncs).

## 7. Open questions

None blocking. Naming (`sme` as the field/dir token vs. `experts`) is settled as `sme` to match the approved previews; trivially renameable before the plan lands if preferred.
