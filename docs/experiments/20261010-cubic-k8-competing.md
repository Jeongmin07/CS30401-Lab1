# K8 versus K20 under CUBIC competition

**Status: completed six-case deterministic extension of PR #12.** kim-seongchan with AI assistance, 2026-10-10. The question and six conditions were declared before execution at **7266051e6ed4cab15c13d59c555ca32f2803e479**. This is independent evidence for team review, not a team-approved parameter choice.

K8 reduces the simultaneous GD first genuine-loss repair penalty from 19.50 to 5.74 ms, but **all three simultaneous-start modes have lower Jain indices than their K20 controls**. In join10, matched K8/K20 observed trajectories are equal after removing verified threshold settings/control events. A smaller local loss penalty does not imply a better allocation under competition.

## Question and fixed comparisons

Does K8 reduce genuine-loss recovery cost without worsening delivered-byte allocation when two CUBIC flows share the route? PR #10's single-flow K8 result does not answer coexistence. Reuse the original eight DD/K20 controls in [the comparison](20261010-cubic-competing.md), pinned to PR #12 head **aa4d4778a95daf310db0a4fb90c6453dec226310**. Preserve their raw data and summaries.

Add exactly six primary conditions: `same-start-gd-k8`, `same-start-dg-k8`, `same-start-gg-k8`, `join10-gd-k8`, `join10-dg-k8`, `join10-gg-k8`. Mode letters still identify flow 0/1. Both starts are 0 for same-start; flow 1 starts at 10 seconds for join10. Every G socket uses `study_threshold=8;study_windows=26100000000:26500000000|74900000000:75300000000`; every D socket retains K3.

Retain the 200-second supplied Seoul–London state, endpoints 1584→1585, 10-Mbit/s ISL/GSL links, 100-packet device queues, 100-GB transfers, CUBIC/SACK/PRR, seed 123456789 and no pacing. Canonical v6 patch, compiled binary and runner stay unchanged. These are PR #12's **26.1–26.5 and 74.9–75.3-second** windows; PR #10's new 121.5–121.9-second target is not imported. The known-size ≤21-MSS exemption does not activate for these bulk flows.

## Declared measurement and validation

- Compare individual app delivery, sum and Jain over common-active intervals: 0–200 or 10–200 seconds. Retain whole run, 20–200-second slice and the two original event windows separately.
- Keep per-flow data retransmissions, recovery/LOSS entries, dropped transmissions, sender SRTT, wire/app byte difference and actual guard/restoration times. Jain alone does not identify whether each competitor benefits.
- Validate two receiver connections, app/bin/count agreement with the unchanged analyzer, initial K3 and each intended K8 activation. Recheck canonical patch/binary/runner identity. Replay one representative K8 case on another fresh official volume.
- Audit the simultaneous GD first genuine-loss episode against DD using transmission tags and ordered delivery. A local delay does not explain every later sharing interaction.
- Store small settings/results and source/trace hashes in Git; archive the six raw bundles outside Git with a manifest. These are deterministic controls, not independent statistical repetitions.

All six cases completed with exit code 0 and passed those checks. The existing eight DD/K20 case bundles and the four window controls were preserved. No simulator source, canonical patch, compiled binary or original runner was changed for K8.

## Delivery allocation under the two start schedules

The table reports **unique ordered application delivery**, with both flow rates divided by the same interval length. DD is the existing K3 baseline; K8/K20 apply only to the G sockets. Jain is calculated from the two delivered-byte totals over that same interval. These deterministic conditions have no confidence intervals.

| Starts / interval | Mode | G policy | Flow 0, Mbit/s | Flow 1, Mbit/s | Sum, Mbit/s | Jain |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 0/0; 0–200 s | DD | none | 4.699783 | 4.879128 | 9.578911 | 0.999650 |
| 0/0; 0–200 s | GD | K20 | 4.361186 | 5.217670 | 9.578856 | 0.992069 |
| 0/0; 0–200 s | GD | K8 | 3.909816 | 5.668874 | 9.578690 | 0.967376 |
| 0/0; 0–200 s | DG | K20 | 4.300301 | 5.279162 | 9.579463 | 0.989666 |
| 0/0; 0–200 s | DG | K8 | 4.084690 | 5.494553 | 9.579242 | 0.978798 |
| 0/0; 0–200 s | GG | K20 | 4.490520 | 5.080663 | 9.571183 | 0.996213 |
| 0/0; 0–200 s | GG | K8 | 5.469989 | 4.104838 | 9.574826 | 0.980077 |
| 0/10; 10–200 s | DD | none | 3.626931 | 5.988270 | 9.615201 | 0.943119 |
| 0/10; 10–200 s | GD | K20 = K8 | 4.397290 | 5.218027 | 9.615317 | 0.992767 |
| 0/10; 10–200 s | DG | K20 = K8 | 3.626931 | 5.988270 | 9.615201 | 0.943119 |
| 0/10; 10–200 s | GG | K20 = K8 | 4.397290 | 5.218027 | 9.615317 | 0.992767 |

Source: [`comparison/windows.csv`](assets/cubic-competing-k8-20261010/comparison/windows.csv), 14 cases × five windows. [`metrics.csv`](assets/cubic-competing-k8-20261010/comparison/metrics.csv) and [`contrasts.csv`](assets/cubic-competing-k8-20261010/comparison/contrasts.csv) retain units, absolute changes and matched DD or K20 references. The new six-case [`results.csv`](assets/cubic-competing-k8-20261010/results.csv), one-second bins, and each case's settings/summary are also retained. [`compare_thresholds.py`](../../code/competing-flows/compare_thresholds.py) validates the actual settings and source hashes before combining the old and new exports.

[`comparison/provenance.json`](assets/cubic-competing-k8-20261010/comparison/provenance.json) retains the combined input/method metadata, CSV hashes/counts and full generated comparison JSON's hash. Git stores table values once in the CSVs; the tool regenerates the full JSON, also retained locally. The five CSVs were checked cell-for-cell against that full output.

For simultaneous GD, K8 flow 0 receives 97,745,400 B versus K20's 109,029,660 B and DD's 117,494,580 B. Its share falls from 45.53% with K20 to 40.82% with K8. The competitor gains, while aggregate delivery changes little. In GG, the winning flow reverses: flow 0's share is 46.92% with K20 and 57.13% with K8. Thus changing K can alter the shared history in either direction; it does not monotonically improve per-flow allocation.

The cost counters also differ by socket. Simultaneous GD has 464/264 retransmission rows with K8 versus 444/262 with K20; GG has 362/344 versus 436/279. These are sender data-RETX trace rows, not distinct loss counts. RECOVERY and LOSS entries are separate state-transition counters; LOSS is not independently instrumented as an RTO counter. Tagged drop counts, SRTT summaries and wire/app totals remain in each case summary. Held sender SRTT is not a raw RTT or an isolated queuing-delay measurement.

### Join10 equality is a complete observed-trace check

[`join-trajectory.json`](assets/cubic-competing-k8-20261010/join-trajectory.json) compares all **15 measurement/legacy CSVs** in each join10 GD, DG and GG K20/K8 pair. It keeps times, UIDs, transmission tags, sequences and every remaining field. Thirteen files are byte-identical for GD and DG, and eleven for GG. The remainder become equal after removing only the `threshold` column and `THRESHOLD_*` events. The actual schedule and complete INIT/SET/RESTORE lifecycle are checked separately before these controls are excluded.

Wall-clock `timing_results.csv` is excluded from trajectory equality and its hash is retained. This establishes equality of the recorded trajectories in these three conditions, not equality of every unlogged internal TCP variable or threshold-insensitivity on other histories. The earlier DD/DG and GD/GG join10 equality controls remain in the [window audit](20261010-cubic-competing-audit.md).

## First real-loss repair: lower local cost, worse whole-run sharing

[`first-loss.json`](assets/cubic-competing-k8-20261010/first-loss.json) reuses the unchanged first-loss auditor on DD versus simultaneous GD-K8. The original `seq=18269821`, `tx_id=13448` is transmitted at 26.133910438 s and directly matched to TcDrop at Seoul node 1584 in both runs. Its original transmission tag does not arrive at the receiver. Before the first differing flow-0 sender row, 20,939 transport-semantic rows match.

| Recovery observation on flow 0 | DD K3 | GD K8 | GD K20 |
| --- | ---: | ---: | ---: |
| First retransmission, seconds | 26.360010740 | 26.365746702 | 26.379513028 |
| Extra retransmission delay versus DD, ms | 0 | 5.735962 | 19.502288 |
| Extra confirmed ordered repair-delivery delay, ms | 0 | 5.736017 | 19.502455 |

K20 evidence comes from the preserved [first-loss audit](assets/cubic-competing-audit-20261010/first-loss.json). K8's repair releases the same 59,340 B batch, with an observed eight-MSS SACK block `18271201:18282241`. The setter changes both duplicate-ACK and presumed-loss thresholds; the trace does not identify which internal predicate fires. It does not reconstruct an internal duplicate-ACK count from SACK span.

The observed simultaneous flow-0 guard restores K3 at **26.736418096 s** for K8 versus **26.746742827 s** for K20, after the requested 26.5-s end. K8 DG flow 1 restores at 26.649039409 s; K8 GG flow 1 at 26.654775370 s. [`guard_intervals.csv`](assets/cubic-competing-k8-20261010/comparison/guard_intervals.csv) records every actual interval and overhang. Comparisons share requested windows and the safe-restoration policy; they do not hold actual high-K duration equal. No separate duration-matched control was run.

K8 therefore lowers this directly observed initial real-loss repair penalty. Yet the GD-K8 whole-run Jain and guarded flow delivery are lower than GD-K20. The local repair difference does not explain every later shared-queue interaction, nor does a whole-run allocation difference alone identify its entire causal chain.

## Terminal delivery and the deadline

[`terminal.csv`](assets/cubic-competing-k8-20261010/comparison/terminal.csv) retains per-flow and aggregate wire-unique versus application totals. In simultaneous GG-K8, flow 0 has no wire/app excess and flow 1 has **107,640 B** of received payload above the final ordered delivery frontier. Relative to DD:

`GG-K8 − DD app bytes = (+5,520 wire-unique bytes) − (107,640 terminal wire/app excess) = −102,120 B`.

The separate [`terminal-gap.json`](assets/cubic-competing-k8-20261010/terminal-gap.json) verifies flow 1's **three 1,380-B missing sequence ranges**. Each joins a tagged original TcDrop at node 1584 and retransmission attempts under restored K3, with no receiver payload overlapping the hole before 200 s. Sender SACK confirms 53,820 B above the final frontier; another 53,820 B lacks sender SACK confirmation at cutoff.

Wire Rx is logged before TCP processing. Flow 1's final wire row at 199.998972522 s has pre-processing `expected_seq=102615421`; the same-time app delivery of 5,520 B advances the final frontier to `102620941`. The auditor checks every payload's pre-processing expected sequence against the actual drained app history and records this final transition. Equating that pre-processing value with the final app frontier would be incorrect. The updated auditor also passed the existing K20 fixture, retaining its previous measurement/accounting evidence ([regression check](assets/cubic-competing-k8-20261010/terminal-audit-regression.json)). The original artifact is preserved.

This is deadline-specific delivery accounting, not an exact accepted-buffer occupancy measurement. The [K20 terminal audit](20261010-cubic-competing-audit.md) separately established its own 194,580-B excess. No drain-period or duration-extension simulation was added, so eventual delivery equality is unknown. A packet not observed by 200 s may still be in flight. Earlier guard causation of every late queue loss remains unisolated.

## Reproduction, source identity and shared raw data

All six new simulation manifests record source revision **7266051e6ed4cab15c13d59c555ca32f2803e479**. Analysis/comparison/audit tools and the final record were added after simulation and are identified by their own hashes. The runner is unchanged (`b844c9919d30262a8903bb460755a8a3cd221c58da2a178fe0f95c80fe360b77`); the canonical patch is unchanged (`473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`); binary SHA-256 is `de9f678113c37a72df7e3215e876f18945c0ccecf9123f60fc8f655f9d9a6eab`. The official image digest is `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`.

[`execution.json`](assets/cubic-competing-k8-20261010/execution.json) records the actual commands, two-worker dispatch and exit codes. Simulation case wall times were 19.11–20.58 s, totaling **119.83 s**; build, dispatch, analysis and audit costs are additional. Runtime depends on the host and is not a speedup claim.

**Fresh replay:** same-start-GD-K8 was rerun using a new official image volume, a clean patch application and rebuild. [`reproduction.json`](assets/cubic-competing-k8-20261010/reproduction.json) records all **15 measurement/legacy CSV hashes**, complete analysis SHA-256 and settings/binary/source/connection/guard checks matching. Only wall-clock timing differs and both hashes are disclosed. This is one representative deterministic replay, not a statistical replicate. The other five K8 conditions passed validation on the first volume.

**Raw archive:** [`cubic-competing-k8-20261010.tar.gz`](https://github.com/Jeongmin07/CS30401-Lab1/releases/download/cubic-competing-20261010/cubic-competing-k8-20261010.tar.gz) is an additional asset in the [existing shared release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/cubic-competing-20261010). It contains six case/config/schedule/full-analysis bundles and all 16 CSVs per case: **120 files**, **359,661,466 B uncompressed**, **63,853,717 B compressed**. SHA-256: `4c0c4ffe7b978d31c3d345c4b63ebdc198b4e07f016070c4be44be52674d8e72`. Every member's size/hash was stream-verified against the embedded and published manifests ([manifest](assets/cubic-competing-k8-20261010/archive-manifest.json), [verification](assets/cubic-competing-k8-20261010/archive-verification.json)). The original twelve-case asset was retained unchanged. Raw traces are outside Git; ns-3 tree/build and constellation state are excluded.

First follow the [original fresh official-container setup](20261010-cubic-competing.md#reproduction-provenance-and-size) and generate the eight DD/K20 controls in a **new** container. With the current PR branch mounted at `/work`, these PowerShell commands add the six K8 cases to that prepared container (called `competing-check` below):

```powershell
$k8Guard = 'study_threshold=8;study_windows=26100000000:26500000000|74900000000:75300000000'
docker exec competing-check python3 /work/code/competing-flows/run_competing.py same-start-gd-k8 --mode GD --guard-parameters $k8Guard
docker exec competing-check python3 /work/code/competing-flows/run_competing.py same-start-dg-k8 --mode DG --guard-parameters $k8Guard
docker exec competing-check python3 /work/code/competing-flows/run_competing.py same-start-gg-k8 --mode GG --guard-parameters $k8Guard
docker exec competing-check python3 /work/code/competing-flows/run_competing.py join10-gd-k8 --mode GD --start1-s 10 --guard-parameters $k8Guard
docker exec competing-check python3 /work/code/competing-flows/run_competing.py join10-dg-k8 --mode DG --start1-s 10 --guard-parameters $k8Guard
docker exec competing-check python3 /work/code/competing-flows/run_competing.py join10-gg-k8 --mode GG --start1-s 10 --guard-parameters $k8Guard
docker exec competing-check python3 /work/code/competing-flows/summarize_competing.py --cases same-start-gd-k8 same-start-dg-k8 same-start-gg-k8 join10-gd-k8 join10-dg-k8 join10-gg-k8 --analyzer /work/code/kim-study/analyze_study.py --path-truth /work/code/kim-study/path_truth_200s.csv --out /tmp/k8-export-new
docker exec competing-check python3 /work/code/competing-flows/compare_thresholds.py --baseline-root /work/docs/experiments/assets/cubic-competing-20261010/cases --k8-root /tmp/k8-export-new --out /tmp/k8-comparison-new
docker exec competing-check python3 /work/code/competing-flows/audit_first_loss.py --baseline /tmp/cs30401-competing/same-start-dd --guarded /tmp/cs30401-competing/same-start-gd-k8 --out /tmp/k8-first-loss-new.json
docker exec competing-check python3 /work/code/competing-flows/audit_k8_join.py --out /tmp/k8-join-new.json
docker exec competing-check python3 /work/code/competing-flows/audit_terminal_gap.py --baseline /tmp/cs30401-competing/same-start-dd --guarded /tmp/cs30401-competing/same-start-gg-k8 --out /tmp/k8-terminal-new.json
docker exec competing-check python3 /work/code/competing-flows/archive_competing.py --cases same-start-gd-k8 same-start-dg-k8 same-start-gg-k8 join10-gd-k8 join10-dg-k8 join10-gg-k8 --out /tmp/k8-raw-new.tar.gz --manifest /tmp/k8-manifest-new.json
```

Use new output paths; retained case/export/audit bundles are not overwritten. The comparison above uses the pinned published DD/K20 exports. To compare newly rerun controls, export those eight cases and pass their `cases/` directory instead. A current-branch reproduction records its actual current source revision; compare the recorded simulator/script/settings hashes and measurement content, not Git revision or wall-clock bytes alone.

## Report use and remaining questions

The [English six-page report outline](../reports/20261010-cubic-report-outline.md) combines the original reordering investigation, genuine-loss costs, PR #10's single-flow refinement and these coexistence counterexamples. It maps each proposed claim to exact evidence and separates teammate results read from experiments executed here. It is a writing structure for review, not a finished or team-approved submission.

The supported candidate narrative is: a temporary threshold guard can avoid premature loss decisions under reordering, but its losses, restoration duration and allocation under competition must be evaluated separately. K8 is a tested compromise in PR #10's single-flow cases; it is **not** a generally better coexistence choice in these simultaneous-start cases. We have not tested PR #10's 121.5-s window here, imperfect notification timing, mixed RTT/routes, more than two flows or independent traffic/seed replications. Requested windows still assume advance knowledge; deployment notification is not implemented.

For other teammates' AI chats: review this record and its linked cases, then check the proposed claim/evidence map against your own results. In particular, confirm that the different second-window schedules and single-flow/coexistence metrics are not conflated. A review request is not evidence of a completed teammate review. Final parameter choice, research title, author names and submission packaging still require the three teammates' agreement.
