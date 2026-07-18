# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""House review gate: a Claude Code PreToolUse hook on the Bash tool.

Wired in .karta/../.claude/settings.json (karta repo tooling, NOT the plugin
surface), beside precommit_gate.py. Reads the PreToolUse payload JSON from
stdin and, for the karta repo's own development, requires that a multi-model
review has been recorded before the maintainer commits a plan (binder) file or
lands a delivery branch on the default branch. It is a pre-commit / pre-merge
check, directly analogous to precommit_gate.py; the review itself is produced
by the roundtable MCP tool the agent runs and filed by scripts/roundtable/run_review.py.

The gate keys on the deterministic fact "a fresh recorded review exists for
this exact content" (the staged binder blob, or the integration branch tip),
never on the review's verdict. Two detections, both by git plumbing and
command text only — never by parsing a diff, never by evaluating a
post-condition a PreToolUse hook cannot see:

  (a) BINDER-COMMIT gate: a git commit that would record a change to a
      .karta/binders/<slug>.json plan file needs a fresh record whose stored
      hash matches the binder content being committed, and the record itself
      must be in the commit.
  (b) INTEGRATION-MERGE gate: on the default branch, a git merge naming a
      karta/*/integration ref needs a fresh record for that branch tip.

git cherry-pick / rebase / reset --hard / a merge --squash then a separate
commit are accepted, documented bypasses of the same class as the escape
hatch: a PreToolUse hook cannot evaluate "will this make the tip an ancestor".

Config .karta/roundtable.json gates the gates: absent or enabled:false turns
everything off; points.plan_commit / points.deliver_merge toggle each detection.
Escape hatch: KARTA_SKIP_ROUNDTABLE=1 in the command text or the environment.
Internal errors fail OPEN (exit 0) so a broken hook never wedges the repo; a
missing or stale record is an expected result that blocks (exit 2), not an
internal error.

  python3 roundtable_gate.py < payload.json    # hook mode, exit 0/2
  python3 roundtable_gate.py --self-test        # embedded fixtures, exit 0/1
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # scripts/hooks/ -> repo root
HELPER = "scripts/roundtable/run_review.py"
CONFIG_PATH = ".karta/roundtable.json"
RECORD_DIR = ".karta/roundtable/"
BRANCH_PREFIX = "branch-"
SKIP_VAR = "KARTA_SKIP_ROUNDTABLE"
INTEGRATION_GLOB = "karta/*/integration"  # the shape the merge gate matches
GIT_TIMEOUT = 30

_SPLIT_RE = re.compile(r"&&|\|\||;|\||\n")
# `git commit` / `git merge`: word-boundary match where anything between the two
# words must be option tokens (each optionally trailing one non-dash argument),
# matching precommit_gate.py's conservative detection.
_COMMIT_RE = re.compile(r"\bgit(?:\s+--?\S+(?:\s+[^-\s]\S*)?)*\s+commit\b")
_MERGE_RE = re.compile(r"\bgit(?:\s+--?\S+(?:\s+[^-\s]\S*)?)*\s+merge\b")
# an integration ref named anywhere in a merge command: karta/<slug>/integration
_INTEGRATION_REF_RE = re.compile(r"\bkarta/[^\s/]+/integration\b")
_BINDER_PATH_RE = re.compile(r"\.karta/binders/([^/\s]+)\.json\b")


def _segments(command: str) -> list[str]:
    return _SPLIT_RE.split(command)


def is_commit_command(command: str) -> bool:
    return any(_COMMIT_RE.search(seg) for seg in _segments(command))


def is_merge_command(command: str) -> bool:
    return any(_MERGE_RE.search(seg) for seg in _segments(command))


def commit_reads_worktree(command: str) -> bool:
    """True when the recorded content is the working tree rather than the index:
    a `-a`/`-am`/`--all` or `--amend` commit, or a pathspec commit naming a
    binder path. Otherwise the plain `git commit` records the staged index."""
    for seg in _segments(command):
        if not _COMMIT_RE.search(seg):
            continue
        toks = seg.split()
        for t in toks:
            if t in ("-a", "--all", "--amend") or (t.startswith("-") and not t.startswith("--")
                                                   and "a" in t[1:] and all(c.isalpha() for c in t[1:])):
                return True
        # pathspec: a binder path appears as a bare token in the commit segment
        if _BINDER_PATH_RE.search(seg):
            return True
    return False


def merged_integration_ref(command: str) -> str | None:
    """The karta/<slug>/integration ref named in a `git merge` segment, or None."""
    for seg in _segments(command):
        if not _MERGE_RE.search(seg):
            continue
        m = _INTEGRATION_REF_RE.search(seg)
        if m:
            return m.group(0)
    return None


def slug_of(binder_path: str) -> str:
    return Path(binder_path).stem


# --- git / helper seams (injected so --self-test needs no real repo) ----------

def _real_git(argv: list[str], input_bytes: bytes | None = None) -> tuple[int, bytes]:
    try:
        proc = subprocess.run(["git", *argv], cwd=ROOT, timeout=GIT_TIMEOUT,
                              input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc.returncode, proc.stdout or b""
    except Exception:
        return 1, b""


def _real_helper(args: list[str], input_bytes: bytes | None) -> int:
    py = sys.executable or "python3"
    try:
        proc = subprocess.run([py, str(ROOT / HELPER), *args], cwd=ROOT, timeout=GIT_TIMEOUT,
                              input=input_bytes, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc.returncode
    except Exception:
        return 1


def _real_read(path: str) -> bytes | None:
    try:
        return (ROOT / path).read_bytes()
    except OSError:
        return None


def _binder_paths(lines: list[str]) -> list[str]:
    out = []
    for ln in lines:
        ln = ln.strip()
        if ln.startswith(".karta/binders/") and ln.endswith(".json") and "/archive/" not in ln:
            out.append(ln)
    return out


def binders_to_check(command: str, git) -> list[str]:
    """The binder plan files this commit would record a change to."""
    code, cached = git(["diff", "--cached", "--name-only"])
    paths = set(_binder_paths(cached.decode(errors="replace").splitlines()) if code == 0 else [])
    if commit_reads_worktree(command):
        code2, wt = git(["diff", "--name-only"])
        if code2 == 0:
            paths |= set(_binder_paths(wt.decode(errors="replace").splitlines()))
        for m in _BINDER_PATH_RE.finditer(command):
            paths.add(f".karta/binders/{m.group(1)}.json")
    return sorted(paths)


def binder_bytes(path: str, command: str, git, read_file) -> bytes | None:
    """The content that will be committed: the working-tree file for -a/-am/
    pathspec/--amend, else the staged blob (git show :<path>)."""
    if commit_reads_worktree(command):
        return read_file(path)
    code, out = git(["show", f":{path}"])
    return out if code == 0 else None


def record_in_commit(slug: str, git) -> bool:
    """The review record must ride in the commit: staged, or already in HEAD."""
    rec = f"{RECORD_DIR}{slug}.json"
    code, cached = git(["diff", "--cached", "--name-only"])
    if code == 0 and rec in cached.decode(errors="replace").splitlines():
        return True
    code2, _ = git(["cat-file", "-e", f"HEAD:{rec}"])
    return code2 == 0


def default_branch(git) -> str:
    code, out = git(["symbolic-ref", "refs/remotes/origin/HEAD"])
    if code == 0:
        ref = out.decode(errors="replace").strip()
        if ref.startswith("refs/remotes/origin/"):
            return ref[len("refs/remotes/origin/"):]
    return "main"


def current_branch(git) -> str:
    code, out = git(["symbolic-ref", "--short", "HEAD"])
    return out.decode(errors="replace").strip() if code == 0 else ""


def _record_cmd(slug_or_branch: str, kind: str) -> str:
    if kind == "branch":
        return (f"<run the roundtable panel, then> ... | python3 {HELPER} "
                f"--record --target {slug_or_branch} --kind branch")
    return (f"<run the roundtable panel, then> ... | python3 {HELPER} "
            f"--record --target {slug_or_branch} --kind binder")


def _deny(reason_core: str, record_cmd: str) -> str:
    return (f"{reason_core} The house roundtable edict requires a fresh recorded "
            f"review under {RECORD_DIR} before this lands. Record one with:\n  {record_cmd}\n"
            f"then retry. For an intentional skip (e.g. the review environment is down), "
            f"prefix the command with {SKIP_VAR}=1 (documented escape hatch).")


def decide(payload, env, git, helper, config, read_file=_real_read) -> tuple[int, str]:
    """(exit_code, stderr_message). Pure over its inputs so --self-test can drive
    it with fabricated payloads and stubbed git/helper."""
    if not isinstance(payload, dict):
        return 0, ""
    tool_input = payload.get("tool_input")
    if payload.get("tool_name", "Bash") != "Bash" or not isinstance(tool_input, dict):
        return 0, ""
    command = tool_input.get("command")
    if not isinstance(command, str):
        return 0, ""
    if f"{SKIP_VAR}=1" in command or env.get(SKIP_VAR) == "1":
        return 0, ""
    if not isinstance(config, dict) or not config.get("enabled"):
        return 0, ""
    points = config.get("points") if isinstance(config.get("points"), dict) else {}

    # (a) binder-commit gate
    if points.get("plan_commit") and is_commit_command(command):
        for path in binders_to_check(command, git):
            slug = slug_of(path)
            data = binder_bytes(path, command, git, read_file)
            if data is None:
                continue  # nothing readable to commit for this path
            rc = helper(["--check", "--target", slug, "--kind", "binder", "--bytes-stdin"], data)
            if rc != 0:
                return 2, _deny(
                    f"Commit blocked: plan file {path} has no fresh recorded review "
                    f"(run_review.py --check found none matching the content being committed).",
                    _record_cmd(slug, "binder"))
            if not record_in_commit(slug, git):
                return 2, _deny(
                    f"Commit blocked: the review record {RECORD_DIR}{slug}.json for {path} is "
                    f"not part of this commit (stage it so the audit trail survives checkout).",
                    _record_cmd(slug, "binder"))

    # (b) integration-merge gate
    if points.get("deliver_merge") and is_merge_command(command):
        ref = merged_integration_ref(command)
        if ref and current_branch(git) == default_branch(git):
            rc = helper(["--check", "--target", ref, "--kind", "branch"], None)
            if rc != 0:
                return 2, _deny(
                    f"Merge blocked: {ref} has no fresh recorded review for its current tip "
                    f"(expected a {RECORD_DIR}{BRANCH_PREFIX}<tip-sha>.json record).",
                    _record_cmd(ref, "branch"))

    return 0, ""


def load_config(git=None) -> dict:
    try:
        return json.loads((ROOT / CONFIG_PATH).read_text())
    except (OSError, ValueError):
        return {}


def hook_main(stdin_text: str, env, git, helper, config) -> tuple[int, str]:
    try:
        payload = json.loads(stdin_text)
    except (ValueError, TypeError):
        return 0, ""
    try:
        return decide(payload, env, git, helper, config)
    except Exception as e:  # fail-open: a broken hook must never wedge the repo
        print(f"roundtable_gate: internal error, failing open: {e}", file=sys.stderr)
        return 0, ""


# --- self-test ----------------------------------------------------------------

def _payload(command: str, tool: str = "Bash") -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": tool,
            "tool_input": {"command": command}}


def _run_self_test() -> int:
    failures = total = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures, total
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail and not ok else ''}")
        failures += 0 if ok else 1
        total += 1

    CFG = {"enabled": True, "points": {"plan_commit": True, "deliver_merge": True}}

    # detection
    check("detect commit", is_commit_command('git commit -m x') and not is_commit_command("git status"))
    check("detect merge", is_merge_command("git merge --no-ff karta/x/integration")
          and not is_merge_command("git status"))
    check("worktree read for -a", commit_reads_worktree("git commit -am x"))
    check("worktree read for --amend", commit_reads_worktree("git commit --amend --no-edit"))
    check("worktree read for binder pathspec", commit_reads_worktree("git commit .karta/binders/x.json -m y"))
    check("staged read for plain commit", not commit_reads_worktree('git commit -m "x"'))
    check("integration ref extracted", merged_integration_ref("git merge --squash karta/foo/integration") == "karta/foo/integration")
    check("no ref for unrelated merge", merged_integration_ref("git merge feature/x") is None)

    # stub git: a staged binder x.json, its record NOT staged but in HEAD; branch tip resolvable
    def git_factory(staged, worktree=None, record_staged=False, record_in_head=True,
                    cur="main", default="main"):
        def git(argv, input_bytes=None):
            a = argv
            if a[:3] == ["diff", "--cached", "--name-only"]:
                names = list(staged)
                if record_staged:
                    names.append(f"{RECORD_DIR}x.json")
                return 0, ("\n".join(names) + "\n").encode()
            if a[:2] == ["diff", "--name-only"]:
                return 0, ("\n".join(worktree or []) + "\n").encode()
            if a[0] == "show":
                return 0, b'{"slug":"x"}'
            if a[:2] == ["cat-file", "-e"]:
                return (0, b"") if record_in_head else (1, b"")
            if a == ["symbolic-ref", "refs/remotes/origin/HEAD"]:
                return 0, f"refs/remotes/origin/{default}\n".encode()
            if a == ["symbolic-ref", "--short", "HEAD"]:
                return 0, f"{cur}\n".encode()
            return 1, b""
        return git

    fresh = lambda args, data: 0
    stale = lambda args, data: 1

    # binder-commit gate
    g = git_factory([".karta/binders/x.json"])
    code, _ = decide(_payload('git commit -m x'), {}, g, stale, CFG)
    check("stale binder record blocks commit (exit 2)", code == 2)
    code, r = decide(_payload('git commit -m x'), {}, g, fresh, CFG)
    check("fresh record + record in HEAD allows commit", code == 0, f"code={code}")
    g2 = git_factory([".karta/binders/x.json"], record_in_head=False)
    code, r = decide(_payload('git commit -m x'), {}, g2, fresh, CFG)
    check("fresh record but record not in commit blocks", code == 2)
    check("record-not-in-commit reason mentions staging", "stage it" in r or "not part of this commit" in r)
    g3 = git_factory([".karta/binders/x.json"], record_staged=True, record_in_head=False)
    code, _ = decide(_payload('git commit -m x'), {}, g3, fresh, CFG)
    check("fresh record staged in same commit allows", code == 0)
    code, _ = decide(_payload('git commit -m x'), {}, git_factory([]), stale, CFG)
    check("commit staging no binder allows", code == 0)
    # -a form reads worktree binder (via the injected file reader, not disk)
    g4 = git_factory([], worktree=[".karta/binders/x.json"])
    read_wt = lambda p: b'{"slug":"x"}'
    code, _ = decide(_payload('git commit -am x'), {}, g4, stale, CFG, read_file=read_wt)
    check("git commit -a with stale worktree-binder record blocks", code == 2)

    # deny reason content
    code, r = decide(_payload('git commit -m x'), {}, git_factory([".karta/binders/x.json"]), stale, CFG)
    check("deny reason names record dir", RECORD_DIR in r)
    check("deny reason names the helper --record", "run_review.py --record" in r)
    check("deny reason names the escape", SKIP_VAR in r)

    # merge gate
    gm = git_factory([], cur="main", default="main")
    code, _ = decide(_payload("git merge --no-ff karta/x/integration"), {}, gm, stale, CFG)
    check("merge of integration on default branch, stale, blocks", code == 2)
    code, _ = decide(_payload("git merge --no-ff karta/x/integration"), {}, gm, fresh, CFG)
    check("merge of integration on default branch, fresh, allows", code == 0)
    goff = git_factory([], cur="feature", default="main")
    code, _ = decide(_payload("git merge --no-ff karta/x/integration"), {}, goff, stale, CFG)
    check("same merge off the default branch allows (not gated)", code == 0)
    code, _ = decide(_payload("git merge feature/y"), {}, gm, stale, CFG)
    check("unrelated merge allows", code == 0)

    # accepted bypasses are not gated
    for cmd in ["git cherry-pick abc123", "git rebase main", "git reset --hard karta/x/integration"]:
        code, _ = decide(_payload(cmd), {}, gm, stale, CFG)
        check(f"accepted bypass not gated: {cmd}", code == 0)

    # escape + config
    code, _ = decide(_payload('KARTA_SKIP_ROUNDTABLE=1 git commit -m x'), {},
                     git_factory([".karta/binders/x.json"]), stale, CFG)
    check("KARTA_SKIP_ROUNDTABLE=1 in command skips", code == 0)
    code, _ = decide(_payload('git commit -m x'), {"KARTA_SKIP_ROUNDTABLE": "1"},
                     git_factory([".karta/binders/x.json"]), stale, CFG)
    check("KARTA_SKIP_ROUNDTABLE=1 in env skips", code == 0)
    code, _ = decide(_payload('git commit -m x'), {}, git_factory([".karta/binders/x.json"]), stale, {})
    check("absent/disabled config allows", code == 0)
    code, _ = decide(_payload('git commit -m x'), {}, git_factory([".karta/binders/x.json"]), stale,
                     {"enabled": True, "points": {"plan_commit": False, "deliver_merge": True}})
    check("plan_commit:false disables only the binder gate", code == 0)
    code, _ = decide(_payload("git merge --no-ff karta/x/integration"), {}, gm, stale,
                     {"enabled": True, "points": {"plan_commit": True, "deliver_merge": False}})
    check("deliver_merge:false disables only the merge gate", code == 0)

    # fail-open
    code, _ = hook_main("not json", {}, git_factory([]), stale, CFG)
    check("malformed payload fails open", code == 0)
    def exploding(argv, input_bytes=None): raise RuntimeError("boom")
    code, _ = hook_main(json.dumps(_payload("git commit -m x")), {}, exploding, stale, CFG)
    check("git exception fails open", code == 0)
    code, _ = decide(_payload("ls -la"), {}, git_factory([]), stale, CFG)
    check("non-command allows", code == 0)

    print(f"\n{total - failures}/{total} checks passed")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return _run_self_test()
    code, message = hook_main(sys.stdin.read(), os.environ, _real_git, _real_helper, load_config())
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
