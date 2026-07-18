#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gate probe for sme-pack-static-suite: pack format validation only.

Thin wrapper (partial coverage, honestly labeled): runs
skills/karta-kaizen/scripts/validate_packs.py (exit 0 clean / 1 findings; per-pack
'<path>: OK' / '<path>: INVALID' + '  - <error>' / '<path>: warning: <w>' lines)
over the built-in packs skills/_shared/sme/*.md and the project overlay
.karta/sme/*.md of the --target repo. platform-native.md is excluded per the
vector card's committed exception — the karta-plan SKILL declares it 'shared
reference data, not a pack'. The card's other probes (mirror parity, prefix
collisions, pin conformance, seed drift) are NOT implemented here yet.

Usage: python3 benchmarks/probes/sme-pack-static-suite.py --target <repo-root>
Prints the probe JSON to stdout; exits 0 whether the packs pass or fail (the
'status' field carries the verdict; a nonzero exit means the probe itself crashed).
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

PROBE_ID = "sme-pack-static-suite"
VALIDATOR = Path("skills/karta-kaizen/scripts/validate_packs.py")
EXCLUDED = {"platform-native.md"}  # shared reference data, not a pack (karta-plan SKILL)
CHECK_TIMEOUT_S = 100


def _collect_packs(target: Path) -> tuple[list[Path], list[str]]:
    packs: list[Path] = []
    excluded: list[str] = []
    for pack_dir in (target / "skills" / "_shared" / "sme", target / ".karta" / "sme"):
        if not pack_dir.is_dir():
            continue
        for p in sorted(pack_dir.glob("*.md")):
            if p.name in EXCLUDED:
                excluded.append(str(p.relative_to(target)))
            else:
                packs.append(p)
    return packs, excluded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=Path,
                    default=Path(__file__).resolve().parent.parent.parent,
                    help="karta repo root (default: this probe's repo)")
    args = ap.parse_args()
    target = args.target.resolve()

    packs, excluded = _collect_packs(target)
    findings: list[dict] = []
    packs_failed = 0
    warnings = 0

    if not packs:
        findings.append({"finding_id": "no-packs-found", "severity": "error",
                         "summary": f"no pack files found under {target}"})
    else:
        rel = [str(p.relative_to(target)) for p in packs]
        try:
            proc = subprocess.run(
                [sys.executable, str(target / VALIDATOR), *rel],
                capture_output=True, text=True, timeout=CHECK_TIMEOUT_S, cwd=str(target))
        except (OSError, subprocess.TimeoutExpired) as e:
            print(json.dumps({
                "id": PROBE_ID, "status": "fail", "partial": True,
                "implemented_checks": ["stack-pack format validation (validate_packs.py)"],
                "findings": [{"finding_id": "validator-not-run", "severity": "error",
                              "summary": f"{VALIDATOR} did not complete ({e})"}],
                "metrics": {"packs_checked": len(packs), "packs_failed": len(packs),
                            "warnings": 0, "excluded": excluded},
            }, indent=2))
            return 0
        current = ""
        for ln in proc.stdout.splitlines():
            if ln.endswith(": INVALID"):
                current = ln[:-len(": INVALID")]
                packs_failed += 1
            elif ": unreadable (" in ln:
                packs_failed += 1
                findings.append({"finding_id": f"pack-unreadable-{packs_failed}",
                                 "severity": "error", "summary": ln})
            elif ": warning: " in ln:
                warnings += 1
                findings.append({"finding_id": f"pack-warning-{warnings}",
                                 "severity": "warning", "summary": ln})
            elif ln.startswith("  - "):
                findings.append({"finding_id": f"pack-invalid-{Path(current).name}-"
                                               f"{sum(1 for f in findings if f['severity'] == 'error') + 1}",
                                 "severity": "error", "summary": f"{current}: {ln[4:]}"})
        if proc.returncode != 0 and packs_failed == 0:
            # fail-closed: validator said failed but nothing parsed as INVALID
            packs_failed = len(packs)
            findings.append({"finding_id": "validator-output-unparsed", "severity": "error",
                             "summary": f"validate_packs.py exit {proc.returncode} "
                                        f"but no INVALID line parsed"})

    print(json.dumps({
        "id": PROBE_ID,
        "status": "fail" if (packs_failed or not packs) else "pass",
        "partial": True,
        "implemented_checks": ["stack-pack format validation (validate_packs.py)"],
        "findings": findings,
        "metrics": {"packs_checked": len(packs), "packs_failed": packs_failed,
                    "warnings": warnings, "excluded": excluded},
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
