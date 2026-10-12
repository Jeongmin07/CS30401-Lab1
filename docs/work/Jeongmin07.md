# Jeongmin07 — current handoff

## Latest follow-up, 2026-10-12

Continued PR15 after checking the original handout pages 3-5: justified TCP and
link-rate changes are allowed, with matched baselines and costs. Ten declared
renewal timing/capacity cases completed at `fbc0b2b01055e51ccfdd0ea33606301e8c9ae4b0`.
The simulator patch is unchanged; adaptive thresholds are OFF. Histories
10/20/40 cycles, fixed 1 ms rise threshold, 100 Mbps LEO/fixed-CUBIC, and
50 Mbps LEO with its own baseline. A credit interruption blocked a status
check but did not stop the batch.

My preferred balanced candidate is now **40 cycles** within PR14's renewal
design: LEO 68.4538 vs r20 69.3432 Mbps; competition queue 3.2477 vs 4.7240 ms,
Jain .999528 vs .968333; aggregate 92.9192 vs 93.8027 Mbps, TcDrop 203 vs 186.
Neither new setting dominates r20. At 50 Mbps r40 gives 40.8433 vs original
25.3262 Mbps. It still renews eight times on a fixed path: no general
congestion/route distinction. This supersedes my earlier exact-r20 preference,
not the team's PLAN or a merge decision.

Audit: 21,840 state rows, 101 renewals, exact 37-file r20 compatibility with
PR14. The Git-free source ZIP at `1deee988a37325c230a389ad4e6dafc518fc138f`
was extracted and run in a new official volume. The representative r40
competition replay matches all 26 measurement CSVs, metrics, simulator sources,
binary, libraries and state audit. An altered source hash was rejected before
simulation. A subsequent complete run of the ZIP README workflow now passes:
all ten cases (1,044.65 seconds including analysis), 155 measurement CSVs,
all windows, the results table and figure PNG match exactly. The separately
rerun original 100 Mbps baseline matches 11 CSVs and all six windows, including
41.5113384 Mbps over 200 seconds. Same fresh volume and unchanged package;
matrix used two workers, with the separate baseline running concurrently.
This closes the research-package workflow gap, not final submission assembly.

Publication is complete: all three assets of release `vegas-sensitivity-20261011`
match server size/SHA256 checks. The failed PowerShell upload timed out; its
stale local response was rejected. The replacement curl upload completed with
HTTP 201, primary asset 632692769. Use committed `publication.json`, not failed
temporary receipts. The release remains a prerelease; PR15 remains Draft.

See [full follow-up](../experiments/20261011-vegas-renewal-sensitivity.md),
`code/vegas-adaptive/sensitivity-evidence/`, and the
[raw/package release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-sensitivity-20261011).
Primary runs: `lab1-vegas-adaptive-20261011:/tmp/vegas-sensitivity`.
Fresh package replay: container `lab1-vegas-portable-20261012`, volume
`lab1-vegas-portable-ns3-20261012`. Preserve all prior containers/volumes.
The host's ignored `runs/` holds the ZIP, extracted package and upload receipts.
Next is the English IEEE report and final assembly with confirmed team scope
and names; the tested research-code ZIP is not `Lab1_5.zip`. No merge performed.

## Current study, 2026-10-11

Branch `experiment/vegas-adaptive-ca`, [PR15](https://github.com/Jeongmin07/CS30401-Lab1/pull/15),
from main `b60e8e0`. User authorized choosing/implementing Docker/GitHub TCP
research; no merge authorized. Reviewed PR10–14 and selected an endpoint-only
Vegas-A-inspired comparator, explicitly reusing selected PR14 inputs pinned at
`4a91c32`. Canonical CUBIC patch and other teammates' branches remain unchanged.

Completed eight matched primary simulations and one fresh-volume adaptive
competition replay at `7ac0751`. LEO 41.5113→50.2036 Mbps; fixed solo
56.2704→79.9932; step 33.8117→52.5680. Fixed-path CUBIC common-window sharing
becomes less equal (Jain .9618→.8275), although aggregate rises 93.2834→95.2006
Mbps and mean queue wait falls 4.0348→2.9264ms. All 75 baseline measurement
CSVs match PR14; fresh replay matches 27 files/source/binary/libraries; all
8,704 adaptive decisions audited, with no base-RTT upward change.

Recommendation: retain PR14 v1 renewal as the primary LEO report candidate
(69.3432Mbps) with its measured congestion-misclassification limitation; keep
PR15 as a comparison. This does not update team PLAN or select a merge.
[Full study and evidence](../experiments/20261011-vegas-adaptive.md).
Raw data: Docker `lab1-vegas-adaptive-20261011` and fresh replay
`lab1-vegas-adaptive-replay-20261011`; [release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-adaptive-20261011).

Prior CUBIC follow-up is completed separately in PR10 (`036c9d8`); its 31-case
fresh replay and 10Mbps oracle-window conclusions are not new Vegas evidence.
The older handoff below is retained as history, superseded by PR10/PR15.

## Previous handoff (historical)

**Branch:** `feat/cubic-study-replication-guide`, based on `main` commit `14a7753`. This work was requested to make the repository understandable and independently continue Seongchan's CUBIC study. It does not change his patch, original evidence, or the team's agreed plan.

## Completed on 2026-10-10

- Replayed the published 100-packet baseline/guarded pair in a fresh Docker ns-3 volume. Both successful full-analysis SHA-256 hashes match the published case records.
- Ran four new 200-second, 75-packet CUBIC cases in the official image: baseline, both route-change windows guarded, first window only, and second window only. The [experiment record](../experiments/20261010-cubic-q75.md) has commands, settings, results, checksums, and limits.
- Replaced the stale root README with a folder map that separates the older 100-Mbit/s `shared-results/` runs from the 10-Mbit/s independent study and shows the canonical patch and evidence locations.

**Observed boundary:** At 75 packets, first-window protection improves its local delivery while lowering 200-second goodput by 0.1997%. First-only reproduces the both-window aggregate; second-only is nearly baseline. The result is deterministic and exploratory, with no independent seeds or second path.

**Raw traces:** retained locally in Docker container `lab1-codex-study-20261010`, `/tmp/cs30401-study/<case>/logs_ns3`. Other laptops can regenerate them from the linked commands. Compact results, run settings, and hashes are in the branch.

## Remaining work

Inspect when the 75-packet run's later deficit accumulates and which packet/drop events cause it. Decide with teammates whether the queue sensitivity belongs in the final narrative. Do not treat this branch's findings as an agreed team direction until reviewed.
