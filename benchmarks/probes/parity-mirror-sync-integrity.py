#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Gate probe for parity-mirror-sync-integrity: wrap the repo's existing checkers.

Thin wrapper (partial coverage, honestly labeled): runs scripts/check_shared_copies.py
(exit 0 IN SYNC / 1 DRIFT with '  - <error>' lines) and scripts/validate_plugin.py
(exit 0 PASS / 1 FAIL with '  - <error>' lines) from the --target repo root and maps
their real results into the probe JSON contract. The vector card's full procedure
(P1 exec-bit projection, P2 lock-degradation survival, P3 external-hash liveness)
is NOT implemented here yet — hence partial: true and the not_implemented metric.

Usage: python3 benchmarks/probes/parity-mirror-sync-integrity.py --target <repo-root>
Prints the probe JSON to stdout; exits 0 whether the checks pass or fail (the
'status' field carries the verdict; a nonzero exit means the probe itself crashed).
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

PROBE_ID = "parity-mirror-sync-integrity"
CHECKS = [
    ("shared-copy byte parity", "shared-copies", Path("scripts/check_shared_copies.py")),
    ("plugin manifest validation", "plugin-integrity", Path("scripts/validate_plugin.py")),
]
CHECK_TIMEOUT_S = 55  # two checks must fit inside the gate's 120s probe budget


def _findings_from(slug: str, output: str) -> list[dict]:
    """One finding per checker '  - <error>' line; the headline line as fallback."""
    lines = [ln[4:] for ln in output.splitlines() if ln.startswith("  - ")]
    if not lines:
        lines = [ln for ln in output.splitlines() if ln.strip()][:1] or ["no output"]
    return [{"finding_id": f"{slug}-{n}", "severity": "error", "summary": ln}
            for n, ln in enumerate(lines, 1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=Path,
                    default=Path(__file__).resolve().parent.parent.parent,
                    help="karta repo root (default: this probe's repo)")
    args = ap.parse_args()
    target = args.target.resolve()

    findings: list[dict] = []
    checks_failed = 0
    for label, slug, script in CHECKS:
        try:
            proc = subprocess.run([sys.executable, str(target / script)],
                                  capture_output=True, text=True,
                                  timeout=CHECK_TIMEOUT_S, cwd=str(target))
        except (OSError, subprocess.TimeoutExpired) as e:
            checks_failed += 1
            findings.append({"finding_id": f"{slug}-not-run", "severity": "error",
                             "summary": f"{script} did not complete ({e})"})
            continue
        if proc.returncode != 0:
            checks_failed += 1
            findings.extend(_findings_from(slug, proc.stdout + proc.stderr))

    print(json.dumps({
        "id": PROBE_ID,
        "status": "fail" if checks_failed else "pass",
        "partial": True,
        "implemented_checks": [label for label, _, _ in CHECKS],
        "findings": findings,
        "metrics": {
            "checks_run": len(CHECKS),
            "checks_failed": checks_failed,
            "not_implemented": ["P1-exec-bit-projection",
                                "P2-lock-degradation-survival",
                                "P3-external-hash-liveness"],
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
