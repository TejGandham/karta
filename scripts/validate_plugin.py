# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Plugin integrity check: SKILL.md frontmatter + reference-link existence.

Usage:
  uv run scripts/validate_plugin.py --self-test   # check this repo, exit 0/1
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
LINK_RE = re.compile(r"\(([^\s)]+\.(?:md|json|py))\)")        # markdown links (no spaces)
PATH_RE = re.compile(r"`(references/[^`]+|scripts/[^`]+)`")    # backticked paths


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm: dict[str, str] = {}
    for line in text[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def check() -> list[str]:
    errors: list[str] = []
    skill_dirs = [p.parent for p in SKILLS.glob("*/SKILL.md")]
    if not skill_dirs:
        errors.append("no skills found under skills/*/SKILL.md")
    for sd in sorted(skill_dirs):
        text = (sd / "SKILL.md").read_text()
        fm = _frontmatter(text)
        for field in ("name", "description"):
            if not fm.get(field):
                errors.append(f"{sd.name}: SKILL.md missing frontmatter '{field}'")
        cited = set(LINK_RE.findall(text)) | set(PATH_RE.findall(text))
        for rel in sorted(cited):
            if rel.startswith(("http://", "https://")):
                continue
            target = (sd / rel).resolve()
            if not str(target).startswith(str(ROOT)):
                continue  # out-of-tree example path, not a repo file
            if not target.exists():
                errors.append(f"{sd.name}: SKILL.md cites missing path '{rel}'")
    # karta-owned agents: frontmatter only (no SKILL-style links)
    for agent in sorted((ROOT / "agents").glob("*.md")):
        fm = _frontmatter(agent.read_text())
        for field in ("name", "description"):
            if not fm.get(field):
                errors.append(f"agents/{agent.name}: missing frontmatter '{field}'")
    # Claude marketplace manifest: a plugin that enumerates skills must list exactly
    # the skill dirs present (a `strict` entry only loads what it lists), so a skill
    # dir added without a manifest line would silently never register.
    present = {sd.name for sd in skill_dirs}
    mp = ROOT / ".claude-plugin" / "marketplace.json"
    if mp.exists():
        try:
            data = json.loads(mp.read_text())
        except json.JSONDecodeError as e:
            errors.append(f".claude-plugin/marketplace.json: invalid JSON ({e})")
            data = {}
        for plugin in data.get("plugins", []):
            listed_raw = plugin.get("skills")
            if not isinstance(listed_raw, list):
                continue  # directory-form ("./skills/") or absent — nothing to enumerate
            listed = {Path(s).name for s in listed_raw}
            pname = plugin.get("name", "?")
            for name in sorted(present - listed):
                errors.append(f"marketplace.json: skill '{name}' exists under skills/ but plugin '{pname}' does not list it")
            for name in sorted(listed - present):
                errors.append(f"marketplace.json: plugin '{pname}' lists '{name}' but skills/{name}/SKILL.md is missing")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.parse_args()
    errors = check()
    if errors:
        print("PLUGIN INTEGRITY: FAIL")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("PLUGIN INTEGRITY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
