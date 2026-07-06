# karta-kaizen — design

- Date: 2026-07-04 (finalized with the owner 2026-07-05)
- Status: design finalized — ready for an implementation plan
- In one line: an opt-in agent that watches your builds, learns what keeps happening, and improves your project's stack packs. It writes knowledge on its own; it never changes what blocks a build without you.

## 1. What kaizen is

Today karta finishes a job and forgets it. If the same kind of item keeps breaking the same rule, karta has no way to notice and nowhere to write it down. kaizen fixes that.

After a delivery, kaizen looks at what happened and turns the repeating patterns into better stack packs. It sharpens rules that keep getting in the way, writes down the knowledge your project relies on, and — the main point — suggests brand-new packs when it spots a gap. It is off until you turn it on. When it's on, every change it makes is a normal commit you review before merging.

It is the learning half of what doc-gardner started. doc-gardner keeps your docs matching your code. kaizen keeps your stack packs matching what your project has learned.

## 2. The core rule (read this first)

Everything below follows from one rule:

**kaizen writes knowledge freely. It never changes what blocks a build on its own. Adding or weakening a gate is your decision — and there, kaizen's job is to explain, not to enforce.**

That splits kaizen's work in two:

- **kaizen acts on its own** (writes the change, commits it, you review the commit): it captures your project's knowledge into packs, writes new packs as *advisory*, sharpens and clarifies existing guidance, and adds narrow exceptions.
- **You decide** (kaizen shows you the pattern and explains it, then waits): loosening a rule that currently blocks builds, and turning a new pack's rules into enforced checks.

Nothing kaizen does can quietly make your checks weaker. That is the whole safety story, and it is why the rest of the design stays simple.

## 3. Where knowledge lives: stack packs, and nothing else

A reminder of what a stack pack is: a short markdown file of guidance for one thing — a technology (Angular, FastAPI) or a part of your domain (billing, auth). Each pack has do's and don'ts and a checklist of rules. karta already checks builds against the packs that match your project, and you can already add your own. Packs are the customization surface — that is what they were built for.

kaizen uses that same surface for *all* the durable knowledge it produces. There is no separate set of knowledge docs. In practice:

- **Your project's vocabulary** (what a "glossary" would hold) lives in a domain pack.
- **The reason behind a rule change** lives in the kaizen commit that made the change — one `git log` away, right next to the edit.
- **Run numbers** (pass rates, override counts) are throwaway signals kaizen reads to decide what to do. They are not knowledge and are not saved as docs.

If it's durable guidance, it goes in a pack. If it's a reason, it's in the commit. If it's a number from one run, it's not kept. That's the whole filing system.

## 4. How packs are stored: your repo owns them

You chose "seed all," and it settles the layering question cleanly.

When you turn kaizen on, karta copies every pack your project uses into `.karta/sme/` as a full, complete file. From then on, **those files are the packs.** The built-in packs that ship inside karta become templates only: they seed the copies, and they still apply for any pack name your repo doesn't have.

So there is never a hidden merge. The rules that gate your build are the files in `.karta/sme/`, readable in one place. kaizen and you edit those files directly. No base-plus-override, no generated merge file, nothing layered out of sight.

The one cost: once your repo owns a pack, it stops picking up changes to karta's built-in version of it. That's a fair trade for "what you read is what runs." A `karta sme diff` command can later show what changed upstream if you ever want to pull a fix in by hand — a detail for the implementation plan, not a blocker.

## 5. The three things kaizen does

### 5a. Sharpens existing packs — and educates before anything gets weaker

When a build has a good reason to break a pack rule, the builder leaves a marker in the code (`KARTA-SME-OVERRIDE`) naming the rule and why. One override is normal. The same rule overridden again and again means the rule doesn't fit your project as written.

What kaizen does depends on which way the fix goes:

- **If the fix makes the rule sharper** — a narrow exception ("this rule doesn't apply to streaming endpoints"), a clearer wording, a better example — kaizen writes it and commits it. You review the commit.
- **If the fix would make the rule weaker** — loosening or removing a check — kaizen does *not* do it. It educates you instead (§7): it shows the pattern, the reasons, and what loosening would let through, and leaves the decision to you.

### 5b. Suggests new packs — the value-add

This is the point of kaizen. As it watches runs, it looks for gaps:

- a part of your domain the project keeps handling the same careful way, with no pack for it;
- a technical pattern that shows up across many items but isn't in any pack you use;
- a failure that keeps coming back that a rule could have caught earlier.

When it finds one, kaizen **writes a new pack and commits it — as advisory.** A new pack carries a frontmatter flag `enforcing: false`; the checker skips an advisory pack's checklist, so builders see its guidance but it does not gate builds yet. You read it, and when you're happy, you promote it by setting `enforcing: true`. (That flag is a small addition to the pack format — the one schema change kaizen needs.)

So the new knowledge reaches your builders right away, but a new gate never appears without you. This is how proactive value and the core rule stay in step.

**An advisory pack is never silent.** Waiting is a visible state, not a quiet one. Until you decide, every run keeps the pack in front of you:

- the gate names the skip — when the checker skips an advisory pack's checklist, its verdict says so by name ("skipped (advisory): billing-domain"), never as a silent pass;
- the run report lists every advisory pack on every run — not just the run that created it — with how long each has been waiting;
- karta-status shows the same list as a decision you owe.

The reminders stop only when you decide: promote the pack (`enforcing: true`) or remove it. There is no third, quiet state. This is the same idiom karta already uses for opted-out oracles, which are reported after every run so nothing slips through unnoticed.

### 5c. Captures domain knowledge

Some of what kaizen learns isn't a rule — it's your project's language and conventions. That goes into a domain pack too, advisory, so the next plan speaks your project's terms. Same path as 5b: written automatically, promoted to enforcing only if and when you choose.

## 6. Turning it on

One small file, off by default, the same shape as doc-gardner's switch:

```json
{ "enabled": true, "focus": "optional note, e.g. 'watch the billing items and the auth rules'" }
```

- Absent, or `"enabled": false` → kaizen never runs.
- `"enabled": true` → it runs after each delivery, and seeds your packs into `.karta/sme/` the first time.
- `"focus"` → a plain nudge about what to watch. Not a task list.

## 7. Educate, not dictate

This is your rule for erosion, and it shapes how kaizen handles anything that would weaken a check.

kaizen does not guard your rules with hard blocks, and it does not quietly loosen them. When it sees a rule wearing down — overridden again and again — it writes you a short, plain note, in its run report and right next to the rule, that says:

- this rule was overridden N times, across these builds;
- here's the reason given each time;
- here's what loosening it would let through — checked against your own past builds, so it's concrete, not hypothetical.

Then you decide. If you loosen it, that's your call, made with your eyes open. If you don't, the rule stands. Either way the wear is now visible instead of silent. kaizen's job is to make sure you never lose a guardrail by accident — not to stop you from choosing to.

## 8. The plain-language rule

Two kinds of writing, two standards:

- **What kaizen says to you** — run reports, the erosion notes, the "I added this pack" summaries, the commit messages you read — **must be plain language.** kaizen always runs its human-facing writing through karta's plain-language standard (the `karta-plainlanguage` skill), so it reads clearly whatever setup it runs in.
- **What goes inside a stack pack** — the rules, the technical do's and don'ts, code symbols, jargon — **does not** need to be plain language. A pack is a technical artifact for the builder and the checker; it should be precise, not simplified.

The line: talking to a human is plain; pack content is technical.

## 9. What keeps it safe

- **kaizen writes only inside `.karta/sme/`** (the packs) and its own small config and report area. It never touches your code, tests, the binder, or karta's installed built-in packs. Every change is a labeled `kaizen:` commit on the branch you already review, and you can revert it like any other.
- **It can't quietly weaken a check.** By the core rule (§2), loosening and promoting-to-enforcing are yours. The most an automatic kaizen commit can do is add advisory guidance or a narrow exception — never remove a gate.
- **Pack edits are syntax-checked before they land**, so a bad edit can't silently break the checker that reads the pack.
- **The honest risk to keep in view:** because builders only flag rules that are *too strict*, the signal kaizen learns from points one way — toward looser rules. We are not fighting that with automation, by your call — erosion is a human decision. We handle it by making every weakening visible and human-made (§7). Worth watching over time; not a reason to gate now.

## 10. What kaizen never does

- Weaken or remove a rule on its own.
- Turn a new pack into an enforced gate on its own.
- Let an advisory pack wait quietly — every run names the packs still awaiting your promote-or-remove decision.
- Edit karta's built-in packs — it owns only your repo's copies.
- Keep a separate pile of knowledge docs — packs are the single home.
- Touch code, tests, the binder, or prose docs (prose is doc-gardner's job).
- Open a PR or push — it stops at a commit on the branch you review.

## 11. Build sequence

Each phase is a small karta binder on its own.

- [x] **Phase 1 — the frame.** (Delivered 2026-07-05 via the kaizen-frame binder; merged to main at v1.13.0.) The `.karta/kaizen.json` switch, the `karta-kaizen` agent and skill, the seed-all step, and the wiring to run after a delivery. kaizen can write and commit packs; you review. Human-facing output goes through `karta-plainlanguage` from day one.
- [ ] **Phase 2 — sharpen and educate.** Read the `KARTA-SME-OVERRIDE` markers, sharpen packs where the fix is safe, and write the plain "this rule is eroding" notes where it isn't.
- [ ] **Phase 3 — the value-add.** Spot gaps and suggest new advisory packs (technical and domain). This is the part that earns kaizen its place. The `enforcing` frontmatter flag and the gate behavior that honors it ship here, as one slice with the first advisory packs (decided 2026-07-05: all phases land before any release, so the flag belongs with its first real consumer). An advisory pack is surfaced on every run — the named gate skip, the run report, and karta-status — until the human promotes or removes it. Spotting some failure patterns may need a light per-run record; add it here if so.
- [ ] **Phase 4 — scheduled look-back.** Run kaizen on a schedule for a periodic review, not only after a delivery.

## 12. File inventory

**Created (canonical, hand-edited):**

- `agents/karta-kaizen.md` — the writer agent, confined to `.karta/sme/` and its own config/report area
- `skills/karta-kaizen/SKILL.md` + `skills/karta-kaizen/agents/openai.yaml`
- `skills/karta-kaizen/references/kaizen-schema.json` + an example `.karta/kaizen.json`
- `docs/how-to/kaizen.md`

**Created (generated — never hand-edit):**

- `.codex/agents/karta-kaizen.toml` (`workspace-write`)
- the bundled `skills/karta-kaizen/references/karta-kaizen.agent.md`
- the `.agents/skills/karta-kaizen/…` and `plugins/karta/skills/karta-kaizen/…` mirrors

**Modified:**

- `skills/karta-deliver/SKILL.md` and `skills/karta-build/SKILL.md` — run kaizen after a delivery when opted in; seed packs on the first run
- the stack-pack format — add the `enforcing` frontmatter flag (default `true` for existing packs; kaizen writes new packs `false`); teach `karta-safety-auditor` to skip an advisory pack's checklist
- `scripts/sync_codex_agents.py` — register the new agent (add it to `BUNDLE_SITE`)
- `scripts/validate_plugin.py` — schema-check `.karta/kaizen.json` when present
- `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` — add the skill, bump versions
- `README.md`, `AGENTS.md` — note the new agent: the second writer (after doc-gardner), the one that edits your stack packs

**Unchanged:** the binder schema and the way a run is driven; the two read-only gate agents; doc-gardner; karta's built-in packs (kaizen edits only your repo's copies); every run's behavior when kaizen is off.

## Appendix — example of a pack kaizen writes

When kaizen spots a gap (§5b) it writes a pack like this — here a *domain* pack, shipped advisory (`enforcing: false`) so it guides builders without gating builds until you promote it. Pack content is technical on purpose; only kaizen's writing *to you* is plain language (§8).

```markdown
---
name: billing-domain
description: How this project handles money, invoices, and refunds. Written by kaizen from repeated billing work.
match: [billing, invoice, refund, payment]
enforcing: false
---

## Do
- Store money as integer minor units (cents), never floats.
- Make every refund idempotent — key it on the original charge id.
- Treat an invoice as immutable once issued; corrections are new credit notes.

## Don't
- Don't recompute a historical invoice's total from current prices.
- Don't delete a charge row — void it, keep the audit trail.

## Review checklist (enforced only once `enforcing: true`)
- [ ] No monetary value is stored or compared as a float.
- [ ] Every refund path passes an idempotency key derived from the charge id.
- [ ] No code path mutates or deletes an issued invoice row.
```

An example opt-in switch (`.karta/kaizen.json`) is shown inline in §6.
