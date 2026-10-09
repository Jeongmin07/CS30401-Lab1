# Jeongmin07 — current handoff

**Branch:** `feat/cubic-study-replication-guide`, based on `main` commit `14a7753`. This work was requested to make the repository understandable and independently continue Seongchan's CUBIC study. It does not change his patch, original evidence, or the team's agreed plan.

## Completed on 2026-10-10

- Replayed the published 100-packet baseline/guarded pair in a fresh Docker ns-3 volume. Both successful full-analysis SHA-256 hashes match the published case records.
- Ran four new 200-second, 75-packet CUBIC cases in the official image: baseline, both route-change windows guarded, first window only, and second window only. The [experiment record](../experiments/20261010-cubic-q75.md) has commands, settings, results, checksums, and limits.
- Replaced the stale root README with a folder map that separates the older 100-Mbit/s `shared-results/` runs from the 10-Mbit/s independent study and shows the canonical patch and evidence locations.

**Observed boundary:** At 75 packets, first-window protection improves its local delivery while lowering 200-second goodput by 0.1997%. First-only reproduces the both-window aggregate; second-only is nearly baseline. The result is deterministic and exploratory, with no independent seeds or second path.

**Raw traces:** retained locally in Docker container `lab1-codex-study-20261010`, `/tmp/cs30401-study/<case>/logs_ns3`. Other laptops can regenerate them from the linked commands. Compact results, run settings, and hashes are in the branch.

## Remaining work

Inspect when the 75-packet run's later deficit accumulates and which packet/drop events cause it. Decide with teammates whether the queue sensitivity belongs in the final narrative. Do not treat this branch's findings as an agreed team direction until reviewed.
