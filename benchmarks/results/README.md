# Bench results

Two layers, both committed:

1. **Vector-local evidence.** Each vector writes dated, machine-diffable JSON to
   its own results dir (`benchmarks/<family>/results/` or
   `benchmarks/results/<name>/`) with stable finding/probe/case IDs and the input
   SHAs it ran against.
2. **Gate results.** `benchmarks/gate/run_gate.py` composes the deterministic
   probes (`benchmarks/probes/<vector-id>.py`) and writes one summary file per
   run to `benchmarks/results/gate/`: karta sha + plugin version, per-vector rows
   (status, partial, counts, metrics), and summary counts. Vectors with no probe
   are recorded SKIPPED — counted loudly, never hidden, never a pass.

File naming: `<YYYY-MM-DD>-<name>.json` (gate: `<YYYY-MM-DD>-gate.json`).

**Append-only rule.** Result files are history: never edit, regenerate, or delete
a previous date's file — corrections land as a new dated run. Re-running on the
same date replaces only that date's file. Denominators stay frozen or
era-partitioned as each vector card specifies.
