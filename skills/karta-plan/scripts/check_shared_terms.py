# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Enforce a binder's declared `shared_terms` against the assembled tree.

A binder may declare canonical strings that several work items must render
byte-identically (see validate_binder.py for the plan-time schema check). This
script is the deliver-time enforcement point: it reads the touched files each
listed item actually produced and fails if a declared term drifted.

Zero dependencies (pure stdlib), so every invocation form behaves identically —
nothing has to be provisioned before it runs:
  uv run --script check_shared_terms.py --binder <path> [root]   # check, exit 0/1
  uv run --script check_shared_terms.py --self-test              # embedded fixtures
  python3 check_shared_terms.py --binder <path> [root]           # also fine — no deps

`root` defaults to the current working directory (the assembled integration
worktree). Matching is exact substring over file bytes: no similarity threshold,
no language assumptions, no parsing — presence of the declared substring is the
whole reference check.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def evaluate_binder(binder: dict, root: Path) -> list[tuple[str, str, list[str], str]]:
    """Return one result per `shared_terms` entry: (id, status, offenders, canonical).

    status is one of:
      "OK"      — every listed item has `canonical` in at least one existing touched file.
      "PENDING" — at least one listed item has no existing touched file under `root`
                  (it is not delivered yet), so the entry is skipped, never failed.
      "FAIL"    — every listed item has files on the tree, but `offenders` lack the term.

    An absent or empty `shared_terms` yields an empty list (a clean no-op pass)."""
    items_by_id = {it["id"]: it for it in binder.get("work_items", []) if isinstance(it, dict)}
    results: list[tuple[str, str, list[str], str]] = []
    for entry in binder.get("shared_terms", []) or []:
        eid = entry.get("id", "<no-id>")
        canonical = entry.get("canonical", "")
        listed = entry.get("items", [])

        # Gather, per listed item, the touched files that actually exist under root.
        per_item_existing: dict[str, list[Path]] = {}
        for iid in listed:
            item = items_by_id.get(iid)
            touches = item.get("touches", []) if isinstance(item, dict) else []
            per_item_existing[iid] = [root / t for t in touches if (root / t).is_file()]

        # If any listed item has produced nothing yet, this entry is not ready to judge.
        if any(not files for files in per_item_existing.values()):
            results.append((eid, "PENDING", [], canonical))
            continue

        needle = canonical.encode("utf-8")
        offenders = [iid for iid, files in per_item_existing.items()
                     if not any(needle in f.read_bytes() for f in files)]
        results.append((eid, "FAIL" if offenders else "OK", offenders, canonical))
    return results


def check(binder: dict, root: Path) -> tuple[int, list[str]]:
    """Evaluate `binder` under `root`; return (exit_code, human-readable lines).

    exit_code is 1 iff any entry is a violation. Pending and satisfied entries pass."""
    lines: list[str] = []
    violations = 0
    for eid, status, offenders, canonical in evaluate_binder(binder, root):
        if status == "FAIL":
            violations += 1
            who = ", ".join(offenders)
            lines.append(
                f"[FAIL] {eid}: item(s) {who} do not render the canonical term {canonical!r} "
                "byte-identically in any touched file")
        elif status == "PENDING":
            lines.append(
                f"[PENDING] {eid}: not every listed item is delivered yet — skipped")
        else:
            lines.append(f"[PASS] {eid}: every listed item renders the canonical term")
    return (1 if violations else 0, lines)


def _run_self_test() -> int:
    import tempfile

    # A realistic canonical substring, including a non-ASCII em dash, so the byte-identity
    # path is exercised (not just ASCII). Mirrors the dogfood string the design cites.
    CANON = "reuses an archived (delivered) slug — the delivered history is shadowed; pick a fresh slug"
    DRIFT = "reuses an archived slug - the history is shadowed; pick a fresh slug"

    def binder(items: list[dict], shared_terms=None) -> dict:
        b = {"slug": "t", "title": "T", "summary": "S", "motivation": "x",
             "scope": {"included": ["x"]}, "work_items": items}
        if shared_terms is not None:
            b["shared_terms"] = shared_terms
        return b

    def item(iid: str, touches: list[str]) -> dict:
        return {"id": iid, "title": iid, "summary": "s", "touches": touches,
                "oracle": {"type": "unit"}}

    cases: list[tuple] = []

    # 1. all items render the term identically -> pass
    cases.append((
        "all items render the term identically",
        binder(
            [item("validator", ["validator.py"]), item("engine", ["engine.py"])],
            [{"id": "shadow", "canonical": CANON, "items": ["validator", "engine"]}],
        ),
        {"validator.py": f"msg = '{CANON}'", "engine.py": f"warn('{CANON}')"},
        0, ("[PASS]",),
    ))

    # 2. one item drifts -> fail, naming the offending item + canonical
    cases.append((
        "one item drifts",
        binder(
            [item("validator", ["validator.py"]), item("engine", ["engine.py"])],
            [{"id": "shadow", "canonical": CANON, "items": ["validator", "engine"]}],
        ),
        {"validator.py": f"msg = '{CANON}'", "engine.py": f"warn('{DRIFT}')"},
        1, ("[FAIL]", "engine", CANON),
    ))

    # 3. an item with no touched files on the tree -> pending, skipped (not failed)
    cases.append((
        "listed item not delivered yet is pending",
        binder(
            [item("validator", ["validator.py"]), item("engine", ["engine.py"])],
            [{"id": "shadow", "canonical": CANON, "items": ["validator", "engine"]}],
        ),
        {"validator.py": f"msg = '{CANON}'"},  # engine.py absent from the tree
        0, ("[PENDING]",),
    ))

    # 4. a binder with no shared_terms -> clean no-op pass (no lines, exit 0)
    cases.append((
        "binder with no shared_terms is a no-op pass",
        binder([item("validator", ["validator.py"])]),
        {"validator.py": "anything"},
        0, (),
    ))

    # 5. canonical present in one of several touched files -> pass
    cases.append((
        "canonical in one of several touched files",
        binder(
            [item("validator", ["a1.py", "a2.py"]), item("engine", ["engine.py"])],
            [{"id": "shadow", "canonical": CANON, "items": ["validator", "engine"]}],
        ),
        {"a1.py": "unrelated", "a2.py": f"msg = '{CANON}'", "engine.py": f"'{CANON}'"},
        0, ("[PASS]",),
    ))

    # 6. an explicitly empty shared_terms list -> clean no-op pass
    cases.append((
        "empty shared_terms list is a no-op pass",
        binder([item("validator", ["validator.py"])], []),
        {"validator.py": "anything"},
        0, (),
    ))

    failures = 0
    for name, b, tree, want_exit, must_mention in cases:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for rel, content in tree.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            code, lines = check(b, root)
        out = "\n".join(lines)
        ok = code == want_exit and all(m in out for m in must_mention)
        # A no-op case must additionally emit no per-entry lines at all.
        if not must_mention and lines:
            ok = False
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: exit={code} lines={lines}")
        if not ok:
            failures += 1

    print(f"\n{len(cases) - failures}/{len(cases)} checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Enforce a binder's declared shared_terms.")
    ap.add_argument("--binder", type=Path)
    ap.add_argument("root", nargs="?", type=Path, default=Path.cwd(),
                    help="repo root to scan (default: cwd)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return _run_self_test()
    if not args.binder:
        ap.error("provide --binder <path> [root] or --self-test")
    if not args.binder.is_file():
        print(f"INVALID: binder file not found: {args.binder}")
        return 1

    binder = json.loads(args.binder.read_text())
    code, lines = check(binder, args.root)
    for ln in lines:
        print(ln)
    if not lines:
        print("no shared_terms declared — nothing to check")
    print("SHARED TERMS: DRIFT" if code else "SHARED TERMS: OK")
    return code


if __name__ == "__main__":
    sys.exit(main())
