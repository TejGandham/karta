# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mirror the canonical skills into Codex real-directory projections.

Codex discovers repo-local skills under `.agents/skills/<name>/SKILL.md`. karta keeps
its canonical skills at `skills/<name>/` (Claude-native). Symlinks are unreliable for
this on Windows (openai/codex#8400), so the mirror is committed real directories kept
byte-identical to the source by this generator and guarded by validate_plugin.py.

Codex marketplace installs also expect marketplace entries to point at a child plugin
directory (`./plugins/<name>`). The `plugins/karta/` install projection is generated
from the same canonical files and uses real directories for the same cross-platform
reason.

`skills/_shared/` has no SKILL.md and is not a skill; it is never mirrored (its files
are already copied into each skill's own `references/`).

Usage:
  uv run scripts/sync_codex_skills.py            # write the Codex projections
  uv run scripts/sync_codex_skills.py --check     # report drift, exit 0/1 (no writes)
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
MIRROR = ROOT / ".agents" / "skills"
CODEX_PLUGIN = ROOT / ".codex-plugin"
INSTALL_PLUGIN = ROOT / "plugins" / "karta"
INSTALL_SKILLS = INSTALL_PLUGIN / "skills"
INSTALL_CODEX_PLUGIN = INSTALL_PLUGIN / ".codex-plugin"


def skill_dirs() -> list[Path]:
    return sorted(p.parent for p in SKILLS.glob("*/SKILL.md"))


def expected() -> tuple[dict[Path, bytes], set[str]]:
    """Map each mirror file path to its expected bytes; plus the set of skill names."""
    files: dict[Path, bytes] = {}
    names: set[str] = set()
    for sd in skill_dirs():
        names.add(sd.name)
        for f in sd.rglob("*"):
            if f.is_file():
                files[MIRROR / sd.name / f.relative_to(sd)] = f.read_bytes()
    return files, names


def expected_install_projection() -> dict[Path, bytes]:
    """Map each marketplace install projection file to its expected bytes."""
    files: dict[Path, bytes] = {}
    for f in CODEX_PLUGIN.rglob("*"):
        if f.is_file():
            files[INSTALL_CODEX_PLUGIN / f.relative_to(CODEX_PLUGIN)] = f.read_bytes()
    for sd in skill_dirs():
        for f in sd.rglob("*"):
            if f.is_file():
                files[INSTALL_SKILLS / sd.name / f.relative_to(sd)] = f.read_bytes()
    return files


def mirror_files() -> list[Path]:
    return [p for p in MIRROR.rglob("*") if p.is_file()] if MIRROR.exists() else []


def mirror_skill_names() -> set[str]:
    return {p.name for p in MIRROR.iterdir() if p.is_dir()} if MIRROR.exists() else set()


def install_projection_files() -> list[Path]:
    roots = [INSTALL_CODEX_PLUGIN, INSTALL_SKILLS]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(p for p in root.rglob("*") if p.is_file())
    return files


def install_projection_skill_names() -> set[str]:
    return {p.name for p in INSTALL_SKILLS.iterdir() if p.is_dir()} if INSTALL_SKILLS.exists() else set()


def projection_drift(want: dict[Path, bytes], have: set[Path], label: str) -> list[str]:
    problems: list[str] = []
    for p, content in sorted(want.items()):
        if not p.exists():
            problems.append(f"{p.relative_to(ROOT)} missing from {label}")
        elif p.read_bytes() != content:
            problems.append(f"{p.relative_to(ROOT)} differs from canonical")
    for p in sorted(have - set(want)):
        problems.append(f"{p.relative_to(ROOT)} orphaned (no canonical source)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report drift without writing")
    args = ap.parse_args()

    want, names = expected()
    install_want = expected_install_projection()
    if not names:
        raise SystemExit("no skills found under skills/*/SKILL.md")
    have = set(mirror_files())
    install_have = set(install_projection_files())
    orphan_dirs = sorted(mirror_skill_names() - names)
    install_orphan_dirs = sorted(install_projection_skill_names() - names)

    if args.check:
        problems = projection_drift(want, have, "mirror")
        for name in orphan_dirs:
            problems.append(f".agents/skills/{name} orphaned (no skills/{name})")
        problems.extend(projection_drift(install_want, install_have, "install projection"))
        for name in install_orphan_dirs:
            problems.append(f"plugins/karta/skills/{name} orphaned (no skills/{name})")
        if problems:
            print("CODEX SKILLS PROJECTIONS: DRIFT")
            for m in problems:
                print(f"  - {m} — run: uv run scripts/sync_codex_skills.py")
            return 1
        print("CODEX SKILLS PROJECTIONS: IN SYNC")
        return 0

    # write mode
    import shutil
    for name in orphan_dirs:
        shutil.rmtree(MIRROR / name)
        print(f"removed orphan .agents/skills/{name}")
    for p in sorted(have - set(want)):
        p.unlink()
        print(f"removed {p.relative_to(ROOT)}")
    for name in install_orphan_dirs:
        shutil.rmtree(INSTALL_SKILLS / name)
        print(f"removed orphan plugins/karta/skills/{name}")
    for p in sorted(install_have - set(install_want)):
        p.unlink()
        print(f"removed {p.relative_to(ROOT)}")
    wrote = 0
    for p, content in sorted(want.items()):
        if not p.exists() or p.read_bytes() != content:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
            wrote += 1
    install_wrote = 0
    for p, content in sorted(install_want.items()):
        if not p.exists() or p.read_bytes() != content:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
            install_wrote += 1
    print(
        "codex projections in sync "
        f"({len(want)} mirror files, {wrote} written/updated; "
        f"{len(install_want)} install files, {install_wrote} written/updated)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
