# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""karta-status engine: derive 'what's next' from binders + git. Zero dependencies.

  uv run --script karta_next.py                       # terminal map (auto-detect .karta/binders)
  uv run --script karta_next.py --json                # the state as JSON (Phase 2's server reads this)
  uv run --script karta_next.py --footer --binder S   # one-line run footer for a binder slug
  uv run --script karta_next.py --self-test           # embedded fixtures, exit 0/1

Order is a topo sort over `after` edges, recomputed every call — never stored. A dangling `after`
is a warning; a cross-binder cycle is an error (and order is null)."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

BINDERS_DIR = Path(".karta/binders")


def _topo_order(after: dict[str, list[str]]) -> list[str] | None:
    """Kahn topo sort. `after[slug]` = the slugs that must come before `slug`. Deterministic
    (slug order among ready nodes). Returns the order, or None if a cycle leaves nodes unplaced."""
    indeg = {n: 0 for n in after}
    succ: dict[str, list[str]] = {n: [] for n in after}
    for n, preds in after.items():
        for p in preds:
            if p in indeg:
                succ[p].append(n)
                indeg[n] += 1
    ready = sorted(n for n in after if indeg[n] == 0)
    out: list[str] = []
    while ready:
        n = ready.pop(0)
        out.append(n)
        for m in sorted(succ[n]):
            indeg[m] -= 1
            if indeg[m] == 0:
                ready.append(m)
        ready.sort()
    return out if len(out) == len(after) else None


def _binder_status(item_ids: list[str], gb: dict) -> str:
    gitems = gb.get("items", {})
    if item_ids and all(gitems.get(i, {}).get("done_in_default") for i in item_ids):
        return "merged"
    if gb.get("integration_exists") or any(gitems.get(i, {}).get("done") for i in item_ids):
        return "in_flight"
    return "not_started"


def _item_status(deps: list[str], gi: dict, done_ids: set[str]) -> tuple[str, list[str]]:
    if gi.get("done"):   return "done", []
    if gi.get("failed"): return "failed", []
    if gi.get("built"):  return "built", []
    if gi.get("branch"): return "building", []
    unmet = [d for d in deps if d not in done_ids]
    return ("blocked", unmet) if unmet else ("ready", [])


def derive_state(binders: list[dict], git_facts: dict) -> dict:
    default_branch = git_facts.get("default_branch", "main")
    gfb = git_facts.get("binders", {})
    by_slug = {b["slug"]: b for b in binders}

    # cross-binder graph: resolve `after`, collect warnings, topo-sort for the order
    slugs = set(by_slug)
    warnings: list[str] = []
    after: dict[str, list[str]] = {}
    for slug, b in by_slug.items():
        resolved = []
        for ref in b.get("after", []) or []:
            if ref in slugs:
                resolved.append(ref)
            else:
                warnings.append(f"binder '{slug}' has a dangling after: '{ref}' (no such binder)")
        after[slug] = resolved
    order = _topo_order(after)
    errors = [] if order is not None else ["cross-binder cycle in `after` — no run order exists"]

    out_binders = []
    status_by_slug: dict[str, str] = {}
    for slug, b in by_slug.items():
        gb = gfb.get(slug, {})
        items = b.get("work_items", [])
        item_ids = [it["id"] for it in items]
        status = _binder_status(item_ids, gb)
        status_by_slug[slug] = status

        gitems = gb.get("items", {})
        done_ids = {i for i in item_ids if gitems.get(i, {}).get("done")}
        detail, counts = [], {k: 0 for k in
                              ("done", "built", "failed", "building", "ready", "blocked")}
        for it in items:
            st, blk = _item_status(it.get("depends_on", []), gitems.get(it["id"], {}), done_ids)
            counts[st] += 1
            entry = {"id": it["id"], "status": st}
            if blk:
                entry["blocked_by"] = blk
            detail.append(entry)
        out_binders.append({
            "slug": slug, "after": after[slug], "status": status,
            "items": {"total": len(items), **counts, "detail": detail},
        })

    # is_next: a not-started binder whose every `after` predecessor is merged
    for ob in out_binders:
        ob["is_next"] = (ob["status"] == "not_started"
                         and all(status_by_slug.get(p) == "merged" for p in ob["after"]))

    order_view = order if order is not None else sorted(by_slug)
    next_action = _next_action(out_binders, order_view)
    return {
        "repo": {"default_branch": default_branch},
        "order": order,                      # None on cycle — derived, never stored
        "binders": _in_order(out_binders, order_view),
        "next_action": next_action,
        "warnings": sorted(set(warnings)),
        "errors": errors,
    }


def _in_order(out_binders: list[dict], order_view: list[str]) -> list[dict]:
    pos = {s: i for i, s in enumerate(order_view)}
    return sorted(out_binders, key=lambda ob: pos.get(ob["slug"], len(pos)))


def _next_action(out_binders: list[dict], order_view: list[str]) -> dict:
    by_slug = {ob["slug"]: ob for ob in out_binders}
    ordered = [by_slug[s] for s in order_view if s in by_slug]

    # 1) an in-flight binder with a failed item — fix/rerun or re-plan
    for ob in ordered:
        if ob["status"] == "in_flight" and ob["items"]["failed"]:
            return {"level": "item", "command": f"karta-deliver {ob['slug']}",
                    "human": f"{ob['slug']} has a halted item — fix and re-run, or re-plan with karta-plan"}
    # 2) an in-flight binder with work left (building/ready/blocked) — resume it
    for ob in ordered:
        if ob["status"] == "in_flight" and (ob["items"]["building"] or ob["items"]["ready"]
                                            or ob["items"]["blocked"]):
            done, total = ob["items"]["done"], ob["items"]["total"]
            return {"level": "item", "command": f"karta-deliver {ob['slug']}",
                    "human": f"resume {ob['slug']} ({done}/{total} done)"}
    # 3) no in-flight work — start the next not-started, unblocked binder
    for ob in ordered:
        if ob.get("is_next"):
            return {"level": "binder", "command": f"karta-deliver {ob['slug']}",
                    "human": f"start {ob['slug']} (its predecessors are merged)"}
    # 4) everything merged
    if ordered and all(ob["status"] == "merged" for ob in ordered):
        return {"level": "done", "command": None,
                "human": "all binders merged — nothing left to run"}
    # 5) work remains but nothing is runnable (blocked / cycle bottleneck)
    return {"level": "blocked", "command": None,
            "human": "no binder is ready to run — check the warnings/errors above"}


_GLYPH = {"merged": "✓", "in_flight": "●", "not_started": "○"}
_ITEM_GLYPH = {"done": "✓", "built": "▣", "failed": "✗", "building": "◐",
               "ready": "·", "blocked": "○"}


def render_terminal(state: dict) -> str:
    lines: list[str] = []
    for w in state["warnings"]:
        lines.append(f"  warning: {w}")
    for e in state["errors"]:
        lines.append(f"  error: {e}")
    route = "   ".join(f"{b['slug']} {_GLYPH[b['status']]}" for b in state["binders"])
    lines.append(route or "(no binders planned yet)")
    for b in state["binders"]:
        if b["status"] == "in_flight":
            it = b["items"]
            lines.append("")
            lines.append(f"{b['slug']}  (current binder)        {it['done']}/{it['total']} done")
            for d in it["detail"]:
                tail = ("  needs " + ", ".join(d["blocked_by"])) if d.get("blocked_by") else ""
                lines.append(f"   {_ITEM_GLYPH.get(d['status'], '?')} {d['id']}  {d['status']}{tail}")
    na = state["next_action"]
    lines.append("  " + "─" * 44)
    if na["command"]:
        lines.append(f"▶ next:  {na['command']}   ({na['human']})")
    else:
        lines.append(f"▶ {na['human']}")
    return "\n".join(lines)


# `built` shows as ▣ (committed, awaiting the orchestrator's merge); `building` as ◐.


def render_footer(state: dict, slug: str) -> str:
    na = state["next_action"]
    cur = next((b for b in state["binders"] if b["slug"] == slug), None)
    head = ""
    if cur:
        it = cur["items"]
        left = it["total"] - it["done"]
        head = f"{slug} {it['done']}/{it['total']}" + (f" · {left} left" if left else " · complete")
    tip = f"▶ {na['command']}" if na["command"] else f"▶ {na['human']}"
    return "  ".join(x for x in (head, tip) if x)


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout
    except OSError:
        return ""


def _default_branch() -> str:
    head = _git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD").strip()
    if head:
        return head.rsplit("/", 1)[-1]
    for cand in ("main", "master"):
        if _git("rev-parse", "--verify", "--quiet", cand).strip():
            return cand
    return "main"


def load_binders(binders_dir: Path = BINDERS_DIR) -> list[dict]:
    out = []
    if binders_dir.is_dir():
        for p in sorted(binders_dir.glob("*.json")):
            try:
                out.append(json.loads(p.read_text()))
            except (OSError, json.JSONDecodeError):
                continue
    return out


def gather_git_facts(binders: list[dict], default_branch: str) -> dict:
    facts = {"default_branch": default_branch, "binders": {}}
    for b in binders:
        slug = b["slug"]
        item_ids = [it["id"] for it in b.get("work_items", [])]
        refs = set(_git("for-each-ref", "--format=%(refname)",
                        f"refs/karta/{slug}/").splitlines())
        integration = bool(_git("rev-parse", "--verify", "--quiet",
                                f"karta/{slug}/integration").strip())
        items = {}
        for i in item_ids:
            base = f"refs/karta/{slug}/item-{i}"
            done = f"{base}/done" in refs
            # `merge-base --is-ancestor` answers via exit code, so call subprocess directly:
            done_in_default = done and subprocess.run(
                ["git", "merge-base", "--is-ancestor", f"{base}/done", default_branch]
            ).returncode == 0
            branch = bool(_git("rev-parse", "--verify", "--quiet",
                               f"karta/{slug}/item-{i}").strip())
            items[i] = {
                "done": done,
                "done_in_default": done_in_default,
                "built": f"{base}/built" in refs,
                "failed": f"{base}/failed" in refs,
                "branch": branch,
            }
        facts["binders"][slug] = {"integration_exists": integration, "items": items}
    return facts


def _run_self_test() -> int:
    new   = {"slug": "s-new",  "motivation": "x", "scope": {"included": ["x"]},
             "work_items": [{"id": "a", "title": "A", "oracle": {"type": "unit"}}]}
    edit  = {"slug": "s-edit", "after": ["s-new"], "motivation": "x", "scope": {"included": ["x"]},
             "work_items": [
                 {"id": "api", "title": "api", "oracle": {"type": "unit"}},
                 {"id": "doc", "title": "doc", "depends_on": ["api"], "oracle": {"type": "unit"}}]}
    deln  = {"slug": "s-del",  "after": ["s-edit"], "motivation": "x", "scope": {"included": ["x"]},
             "work_items": [{"id": "a", "title": "A", "oracle": {"type": "unit"}}]}
    binders = [new, edit, deln]

    facts = {"default_branch": "main", "binders": {
        "s-new":  {"integration_exists": False,
                   "items": {"a": {"done": True, "done_in_default": True}}},
        "s-edit": {"integration_exists": True, "items": {
            "api": {"done": True, "done_in_default": False},
            "doc": {"branch": False}}},
        "s-del":  {"integration_exists": False, "items": {"a": {}}},
    }}
    st = derive_state(binders, facts)

    checks = [
        ("order is topo-sorted", st["order"] == ["s-new", "s-edit", "s-del"]),
        ("new is merged",  st["binders"][0]["status"] == "merged"),
        ("edit is in-flight", st["binders"][1]["status"] == "in_flight"),
        ("del is not-started", st["binders"][2]["status"] == "not_started"),
        ("doc is ready (api done)", any(d["id"] == "doc" and d["status"] == "ready"
                                        for d in st["binders"][1]["items"]["detail"])),
        ("next action resumes edit", st["next_action"]["command"] == "karta-deliver s-edit"),
        ("no warnings/errors", st["warnings"] == [] and st["errors"] == []),
        ("del not yet is_next (edit unmerged)", st["binders"][2]["is_next"] is False),
    ]

    dangle = derive_state([{"slug": "z", "after": ["ghost"], "motivation": "x",
                            "scope": {"included": ["x"]},
                            "work_items": [{"id": "a", "title": "A", "oracle": {"type": "unit"}}]}],
                          {"default_branch": "main", "binders": {"z": {"items": {"a": {}}}}})
    checks.append(("dangling after warns", len(dangle["warnings"]) == 1 and dangle["errors"] == []))

    cyc = derive_state(
        [{"slug": "ca", "after": ["cb"], "motivation": "x", "scope": {"included": ["x"]},
          "work_items": [{"id": "a", "title": "A", "oracle": {"type": "unit"}}]},
         {"slug": "cb", "after": ["ca"], "motivation": "x", "scope": {"included": ["x"]},
          "work_items": [{"id": "a", "title": "A", "oracle": {"type": "unit"}}]}],
        {"default_branch": "main", "binders": {"ca": {"items": {"a": {}}},
                                               "cb": {"items": {"a": {}}}}})
    checks.append(("cycle -> order None + error", cyc["order"] is None and len(cyc["errors"]) == 1))

    # the renderers must not raise on a real state
    try:
        render_terminal(st); render_footer(st, "s-edit"); rendered = True
    except Exception as exc:                                   # noqa: BLE001
        rendered = False; print(f"render raised: {exc}")
    checks.append(("renderers run", rendered))

    failures = 0
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        failures += 0 if ok else 1
    print(f"\n{len(checks) - failures}/{len(checks)} checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--footer", action="store_true")
    ap.add_argument("--binder", type=str)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return _run_self_test()
    binders = load_binders()
    state = derive_state(binders, gather_git_facts(binders, _default_branch()))
    if args.json:
        print(json.dumps(state, indent=2))
    elif args.footer:
        print(render_footer(state, args.binder or ""))
    else:
        print(render_terminal(state))
    return 0


if __name__ == "__main__":
    sys.exit(main())
