# CUBIC competition: first intervention and terminal delivery audit

**Status: completed deterministic follow-up to [the eight-case comparison](20261010-cubic-competing.md), PR #12.** kim-seongchan with AI assistance, 2026-10-10. Four additional simulations and three trace audits were completed. This is independent evidence for team review, not a final topic decision.

The first guard interval reproduces the GD delivery allocation in both tested start schedules; the second interval alone reproduces DD. In simultaneous-start GD, the first transport difference is a **19.5-ms delay in repairing an actually dropped packet**. Separately, the GG application's 200-second deficit is accounted for by received bytes above unresolved terminal sequence holes. These are narrower findings than a general fairness or network-efficiency claim.

## Controls: which guard interval matters?

Keep the original 10-Mbit/s links, 100-packet queues, two 100-GB CUBIC flows, 200-second Seoul–London state, seed, no pacing and canonical v6 patch. Retain the two starts, 0/0 and 0/10 seconds. In each schedule add only:

- `*-gd-first`: K20 on flow 0 at 26.1–26.5 seconds, with the existing safe restoration behavior.
- `*-gd-later`: K20 on flow 0 at **74.9–75.3 seconds**.

Reuse the existing DD and GD-with-both-windows controls without rerunning or editing them. The table uses 0–200 seconds for simultaneous starts and **10–200 seconds** for join10. First/later are guard policies on flow 0, not new TCP implementations.

| Starts | Policy | Flow 0, Mbit/s | Flow 1, Mbit/s | Sum, Mbit/s | Jain |
| --- | --- | ---: | ---: | ---: | ---: |
| 0 / 0 | DD | 4.699783 | 4.879128 | 9.578911 | 0.999650 |
| 0 / 0 | GD, both | 4.361186 | 5.217670 | 9.578856 | 0.992069 |
| 0 / 0 | GD, first only | 4.361186 | 5.217670 | 9.578856 | 0.992069 |
| 0 / 0 | GD, later only | 4.699783 | 4.879128 | 9.578911 | 0.999650 |
| 0 / 10 | DD | 3.626931 | 5.988270 | 9.615201 | 0.943119 |
| 0 / 10 | GD, both | 4.397290 | 5.218027 | 9.615317 | 0.992767 |
| 0 / 10 | GD, first only | 4.397290 | 5.218027 | 9.615317 | 0.992767 |
| 0 / 10 | GD, later only | 3.626931 | 5.988270 | 9.615201 | 0.943119 |

Source: [`ablation.csv`](assets/cubic-competing-audit-20261010/ablation.csv), with byte counts, retransmissions and recovery counts; [`results.csv`](assets/cubic-competing-audit-20261010/results.csv) retains all five intervals for the new cases. Each new case's configuration, schedule, guard validation and all raw CSV hashes are under [`cases/`](assets/cubic-competing-audit-20261010/cases/).

This equality extends beyond rounded goodput. [`trajectory-equality.json`](assets/cubic-competing-audit-20261010/trajectory-equality.json) compares **15 complete CSVs per pair**, retaining row order, time, congestion state, sequence numbers, packet UIDs and transmission tags, including the final flow summary. It removes only the `threshold` column and `THRESHOLD_*` control events. Only `timing_results.csv` (wall-clock profiling) is outside this comparison. Thirteen of the 15 files are already byte-identical; the protected socket's sender event/packet files normalize to identical rows in each pair. Actual configuration hashes are checked against each other and the manifests.

All six declared pairs match: first-only versus both, later-only versus DD for both schedules, plus original join10 DD/DG and GD/GG. Intended threshold changes were checked separately by the existing exporter. Thus the first interval is sufficient to reproduce GD's observed trajectory here, and adding the later interval does not change that trajectory. This does not reveal every internal duplicate-ACK counter or SACK-scoreboard decision. It also does not prove the late guard will be ineffective on another history, path or queue.

## First difference: genuine loss repair is delayed

[`first-loss.json`](assets/cubic-competing-audit-20261010/first-loss.json) links original transmissions, tagged drops, ACK/SACK, recovery entry, retransmission, receiver observation and ordered application delivery. It also records the first semantic difference in each sender, receiver, application, congestion and drop trace. Port 49153/receiver connection 0 is flow 0; port 49154/connection 1 is flow 1.

| Event on flow 0 | DD, seconds | GD, seconds |
| --- | ---: | ---: |
| Original `seq=18269821`, `tx_id=13448`, actually dropped | 26.133910438 | 26.133910438 |
| First recovery and retransmission of that sequence | 26.360010740 | 26.379513028 |
| Repair arrives; same-time 59,340 B ordered app delivery | 26.537688916 | 26.557191371 |

The original is directly matched by flow ID, transmission ID and transmission time to **TcDrop at Seoul node 1584** in both runs (`study_drops.csv:322`). Its original tag never reaches the receiver in either trace. This is an actual loss, not a successfully delivered original unnecessarily retransmitted.

Before the first differing sender row, 20,939 flow-0 transport-semantic rows match. At 26.360010740 seconds, DD retransmits the hole and enters RECOVERY; GD sends new data and stays in DISORDER. DD's observed SACK block spans three MSS, `18271201:18275341`; GD later repairs the hole with a block spanning twenty MSS, `18271201:18298801`. The retransmission delay is **19.502288 ms** and the confirmed ordered-delivery delay is **19.502455 ms**. Receiver `expected_seq` is a pre-processing observation; same-time app delivery and the following sequence advance independently support the repair result. App packet UIDs are not joined to wire packets.

The source setter changes both the socket duplicate-ACK threshold and the transmission-buffer presumed-loss threshold (`tcp-socket-base.cc:4708–4711`). Recovery tests are in `:1857–1870`; SACK-based loss marking is in `tcp-tx-buffer.cc:866–909`. Existing traces do not expose which predicate fires, so a three/twenty-MSS SACK block is an observation, not a reconstructed internal duplicate-ACK count. `traffic-control-layer.cc:373–390` shows TcDrop when no root queue disc exists and the outgoing transmit queue is stopped. The logged sentinel device index does not locate a specific output interface or establish a unique bottleneck.

GD remains in RECOVERY at the requested 26.5-second guard end and restores K3 at **26.746742827 seconds**, when it returns to OPEN. The delay beyond the requested end is an observed consequence of safe restoration. The original study already recorded it; it is not an independently isolated cause of the eventual share difference.

Taken with the window controls, the evidence identifies the first intervention and its initial real-loss repair delay. It does **not** assign the entire guarded flow's 7.20% whole-run decline to those 19.5 ms. Subsequent transmissions, arrivals, drops and the unchanged competitor's congestion trajectory diverge and interact through shared queues; no per-hop timing trace decomposes every later interaction.

## Terminal GG deficit: ordered delivery versus received bytes

The original GG result had 193,200 fewer application bytes than DD. [`terminal-gap.json`](assets/cubic-competing-audit-20261010/terminal-gap.json) independently reconstructs receiver sequence unions, verifies SYN sequence 0/data sequence 1 and separate connections, checks the unchanged analyzer, and joins each final hole to its dropped original and retransmission attempts.

| GG socket | Final app sequence frontier | Received bytes above frontier | Unreceived holes below highest received end |
| --- | ---: | ---: | ---: |
| Flow 0 | 112263001 | 77,280 B | 4 × 1,380 B |
| Flow 1 | 127016581 | 117,300 B | 1 × 1,380 B |

All five holes have tagged originals rejected by TcDrop at node 1584 shortly before 200 seconds. Retransmission attempts start at 199.914663617 seconds for flow 0 and 199.867473081 seconds for flow 1; no receiver payload overlaps any of these holes before the cutoff. At these retransmissions both senders use restored **K3**, not an active K20 guard. Absence before the cutoff does not prove a retransmission is lost or would never arrive.

The measured accounting is exact:

`GG − DD app bytes = (+1,380 wire-unique bytes) − (194,580 bytes received above unresolved frontiers) = −193,200 B`.

DD has no terminal wire/app excess. GG's sequence holes therefore account for its deadline-specific application deficit. Wire Rx is logged before TCP processing, so **194,580 B is not an exact accepted-buffer occupancy measurement**. Sender-observed SACK confirms all 77,280 B above flow 0's frontier and 57,960 B above flow 1's frontier; the remaining 59,340 B lacks sender SACK confirmation by the cutoff. This supports a subset's out-of-order acceptance without silently treating all late wire observations as accepted.

No drain period or duration-extension control was run. The accounting does not establish identical eventual delivery, the reason every late packet was dropped, or long-run superiority of either policy. Earlier guard causation of the precise terminal queue history is also not isolated by this DD/GG diagnostic.

## Relation to the other teammate's current work

[PR #10](https://github.com/Jeongmin07/CS30401-Lab1/pull/10), reviewed at **036c9d84653a92944705c8af9d88313d3402443d**, is now ready for review. It is a different, single-flow q75 investigation. Its new second target is **121.5–121.9 seconds**, whereas this comparison preserves **74.9–75.3 seconds**. PR #10's K8 plus known-size exemption matches K20's reported bulk delivery in its tested LEO conditions while reducing a 22-MSS real-loss cost; K8 does not preserve K20's synthetic 80-MSS reordering benefit. Those teammate experiments were read, not rerun here.

The two investigations support evaluating local recovery, total delivery, competitor delivery and genuine-loss costs separately. This audit initially covered K20 only. The later [six-case K8 extension](20261010-cubic-k8-competing.md) evaluates K8 with this comparison's original windows; the new 121.5-second window remains untested here. No final shared parameter or research topic is chosen by either PR.

## Provenance, raw archive and reproduction

Original eight cases used source revision **95c306d**; the four new cases used **d5dcdce5cdfa9f3098a52ab7f449e3f6fe87f9f1**. The unchanged runner, canonical patch, binary, official image and helper hashes agree. New audits were added after simulation and are identified separately by their script hashes. The new simulations took **19.31–19.43 seconds each**, totaling **77.47 seconds of case wall time**, with two workers. Build, analysis, archive and audit costs are additional. [`execution.json`](assets/cubic-competing-audit-20261010/execution.json) records the actual commands and dispatch results.

The [shared raw-data release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/cubic-competing-20261010) contains the twelve original case/settings bundles, all CSVs including timing, and full analyses: **719,580,564 B uncompressed**, **127,751,029 B compressed**. The archive is outside Git history. Its SHA-256 is `ba03cfbe60d42ccc9486fb65a151c8d0d6823ef2c2e041636716e69c49a5ae79`. [`archive-manifest.json`](assets/cubic-competing-audit-20261010/archive-manifest.json) identifies all 240 files; [`archive-verification.json`](assets/cubic-competing-audit-20261010/archive-verification.json) records successful streamed size/hash verification of every member. No ns-3 tree/build or constellation state is included.

To regenerate, first follow the original record's fresh official-container setup and eight runs, using a new container/volume. In that **new** container (shown below as `competing-check`), add these controls. All scripts refuse to overwrite existing case/audit/export paths.

```powershell
docker exec competing-check python3 /work/code/competing-flows/run_competing.py same-start-gd-first --mode GD --parameters0 'study_threshold=20;study_windows=26100000000:26500000000'
docker exec competing-check python3 /work/code/competing-flows/run_competing.py same-start-gd-later --mode GD --parameters0 'study_threshold=20;study_windows=74900000000:75300000000'
docker exec competing-check python3 /work/code/competing-flows/run_competing.py join10-gd-first --mode GD --start1-s 10 --parameters0 'study_threshold=20;study_windows=26100000000:26500000000'
docker exec competing-check python3 /work/code/competing-flows/run_competing.py join10-gd-later --mode GD --start1-s 10 --parameters0 'study_threshold=20;study_windows=74900000000:75300000000'
docker exec competing-check python3 /work/code/competing-flows/summarize_competing.py --cases same-start-gd-first same-start-gd-later join10-gd-first join10-gd-later --analyzer /work/code/kim-study/analyze_study.py --path-truth /work/code/kim-study/path_truth_200s.csv --out /tmp/competing-ablation-export

docker exec competing-check python3 -c "from pathlib import Path; Path('/tmp/competing-audit-new').mkdir()"
docker exec competing-check python3 /work/code/competing-flows/audit_trajectory.py --out /tmp/competing-audit-new/trajectory-equality.json
docker exec competing-check python3 /work/code/competing-flows/audit_first_loss.py --baseline /tmp/cs30401-competing/same-start-dd --guarded /tmp/cs30401-competing/same-start-gd --out /tmp/competing-audit-new/first-loss.json
docker exec competing-check python3 /work/code/competing-flows/audit_terminal_gap.py --baseline /tmp/cs30401-competing/same-start-dd --guarded /tmp/cs30401-competing/same-start-gg --out /tmp/competing-audit-new/terminal-gap.json
```

`archive_competing.py --out /tmp/new-raw.tar.gz --manifest /tmp/new-receipt.json` can archive those completed cases. Archive bytes/creation times and wall-clock timing are not expected to reproduce. Compare measurement hashes and calculated metrics instead. The earlier representative GD replay on a separate fresh official volume remains valid; the four new controls were validated, not independently replayed on another volume. These are deterministic controls, not additional statistical replicates.

The team can review the linked JSON/log excerpts and code before adopting a claim. Remaining generalization work includes other paths/traffic histories and imperfect notification timing; reconstructing every long-run queue interaction is outside this completed audit.
