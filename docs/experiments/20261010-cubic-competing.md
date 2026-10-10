# CUBIC reordering guard: competing flows

**Status: completed exploratory comparison.** kim-seongchan with AI assistance, 2026-10-10. Based on merged `main` **b60e8e0**; the runner was executed from commit **95c306d**. This is an independent follow-up, not a team-approved topic. The [literature/context PR #11](https://github.com/Jeongmin07/CS30401-Lab1/pull/11) motivates the comparison. [Jeongmin07's Draft PR #10](https://github.com/Jeongmin07/CS30401-Lab1/pull/10) investigates the q75 deficit/K4/later-event/genuine-loss question; those controls are not repeated here.

## Question and declared comparisons

When two CUBIC flows share the same LEO route and device queues, does temporary reordering tolerance improve delivery without reducing the unchanged competitor's share? Single-flow event-local improvement does not answer that question. Both an effect on total delivery and a redistribution between flows are possible; neither is assumed as a result.

Preserve the official 200-second Seoul 1584 → London 1585 state, 100-ms route updates, CUBIC/SACK/PRR, no pacing, 10-Mbit/s ISL/GSL, 100-packet device queues, seed 123456789, and two 100-GB bulk transfers. Reuse canonical **v6 `code/kim-study/ns3.patch` unchanged**. Guard requests K20 at 26.1–26.5 and 74.9–75.3 seconds; actual restoration can be later. These are known simulation times, not implemented real notifications.

Two start schedules are declared: **0/0 s** and **0/10 s**. For each, compare **DD** (both default), **GD** (only flow 0 guarded), **DG** (only flow 1 guarded), and **GG** (both guarded): eight deterministic cases. Swapping which flow is guarded tests sensitivity to scheduler order/earlier flow, rather than assuming flow IDs are interchangeable. The later-start case checks an additional startup history. It does not establish fairness across other RTTs or paths.

## Why the flows share queues

Read the actual official source in a fresh container: `scratch/main_satnet/main_satnet.cc:79–81` installs `ArbiterSingleForwardHelper`; `contrib/satellite-network/model/arbiter-single-forward.cc:43–50` selects next hop by destination node, without flow/port hashing. `arbiter-satnet.cc:58–73` selects its output interface; GSL/laser devices enqueue on shared `m_queue`. Thus the two identical endpoint flows use the same forwarding state and directed device queues at the same time. This does not identify a unique bottleneck location or prove observed congestion before execution.

`contrib/basic-sim/helper/apps/tcp-flow-scheduler.cc:34–45,128–135` creates a sender per schedule row and one port-1024 sink per endpoint. `tcp-flow-schedule-reader.cc:79–97` requires IDs 0/1 and nondecreasing starts. The v6 receiver logs separate accepted connections and their application bytes by flow ID. Execution must verify both connections, distinct peer sockets, both sender logs, and guard changes only on the requested sockets.

## Measurement and evidence plan

- Receiver application delivery per flow and sum, whole 200 seconds and **common scheduled-active period** (0–200 or 10–200). Also report 20–200 s and the original event windows 25.7–28.2 / 74.5–77.0 s. These are half-open intervals, with equal denominators for both flows.
- Jain fairness and delivered-byte shares over those intervals, plus one-second delivery bins. Whole-run averages can conceal local starvation; Jain alone also cannot show whether total delivery improved.
- Per-flow retransmission rows, recovery/LOSS state entries, distinct tagged dropped transmissions, time-weighted sender SRTT, and actual guard intervals. SRTT is not isolated queue delay; LOSS entries are not automatically RTO counts.
- Reuse `analyze_study.py` unchanged, then independently sum app payload bytes and validate connection totals, sender flow IDs, event/retx counts, and bin totals. Do not double-count `sink_total_rx_bytes`, which combines both flows.
- Store exact schedule/config/case manifests, compact metrics and all trace hashes under `assets/cubic-competing-20261010/`. Raw traces/full analysis remain in the experiment container; record regeneration commands. Repeat a representative condition on another fresh official volume to check reproducibility, not to create a statistical replicate.

The fresh local container is `lab1-competing-20261010`; its ns-3 volume is `cs30401-competing-ns3-20261010`. It is separate from earlier containers/volumes. The official image digest is `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`. Scripts live in `code/competing-flows/` and use the Python standard library.

## Measured delivery and sharing

All eight simulations and trace validations succeeded. The measurements below use **the same interval for both flows**: 0–200 s for simultaneous starts, **10–200 s** for the join condition. D/G label flow 0/1, not the winning/losing flow. Delta is against DD with the same start schedule. Jain uses each interval's cumulative app bytes; it is not instantaneous fairness. The separately declared 20–200 s slice is named `steady` in the CSV as a measurement label, not proof of convergence.

| Starts, s | Mode | Flow 0, Mbit/s | Flow 1, Mbit/s | Sum, Mbit/s | Sum change vs DD | Jain |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0 / 0 | DD | 4.699783 | 4.879128 | 9.578911 | — | 0.999650 |
| 0 / 0 | GD | 4.361186 | 5.217670 | 9.578856 | −0.000576% | 0.992069 |
| 0 / 0 | DG | 4.300301 | 5.279162 | 9.579463 | +0.005763% | 0.989666 |
| 0 / 0 | GG | 4.490520 | 5.080663 | 9.571183 | −0.080677% | 0.996213 |
| 0 / 10 | DD | 3.626931 | 5.988270 | 9.615201 | — | 0.943119 |
| 0 / 10 | GD | 4.397290 | 5.218027 | 9.615317 | +0.001209% | 0.992767 |
| 0 / 10 | DG | 3.626931 | 5.988270 | 9.615201 | 0% | 0.943119 |
| 0 / 10 | GG | 4.397290 | 5.218027 | 9.615317 | +0.001209% | 0.992767 |

Source: [`results.csv`](assets/cubic-competing-20261010/results.csv). It also contains 0–200 s, 20–200 s, both event windows, and per-flow data retransmission/recovery/LOSS counts. [`one_second_bins.csv`](assets/cubic-competing-20261010/one_second_bins.csv) preserves shorter delivery/share behavior. Per-case [`summary.json`](assets/cubic-competing-20261010/cases/same-start-gd/summary.json) files contain SRTT, tagged drop counts, actual protection intervals, connection/guard validation, and hashes.

**Observation: redistribution can be large while total delivery barely changes.** At simultaneous start, GD's guarded flow 0 loses **7.2045%**, while its default competitor gains **6.9386%**; DG's guarded flow 1 gains **8.1989%**, while default flow 0 loses **8.5000%**. Thus a guard is not uniformly advantageous even to the socket using it. The total byte differences from DD are −1,380 bytes for GD and +13,800 bytes for DG; they are not evidence of a substantial aggregate improvement.

For join10 GD, over **10–200 s**, guarded early flow 0 gains **21.2400%** and default late flow 1 loses **12.8625%**. Jain improves from 0.943119 to 0.992767, but the total increases by only **2,760 bytes (2 MSS)**. Better balance and an individual competitor's loss can coexist. Over 0–200 s the early flow's increase is 19.0003%, so the 21.24% result must retain its interval. This is an observed redistribution in this deterministic setup, not evidence that guarded flows always capture competitors' bandwidth.

Join10 DG has the same displayed delivery/counters/SRTT as DD; GG has the same as GD. The intended K20 changes were verified on every G socket at both requested starts, so this equality is not a missing-guard configuration. Guard trace events still differ; aggregate equality is not a claim that all raw files match. Why the late socket's guard leaves these metrics unchanged remains unverified.

## Transient effects and actual protection time

In join10 GD, first-event sum goodput increases **3.8608%** (9.264768→9.622464 Mbit/s), yet whole-run sum improves only **0.00116%**. Its guarded flow 0's event data retransmissions increase 5→15. Therefore this experiment cannot be summarized as removing all unnecessary retransmissions; actual versus spurious retransmissions need packet-level analysis.

The first requested guard ends at 26.5 s, but recovery-state safety causes later restoration in simultaneous-start cases:

| Case/socket | Actual first interval, s | Delay beyond requested end |
| --- | --- | ---: |
| same-start GD, flow 0 | 26.1–26.746742827 | 246.742827 ms |
| same-start DG, flow 1 | 26.1–26.662805724 | 162.805724 ms |
| same-start GG, flow 0 | 26.1–26.746742827 | 246.742827 ms |
| same-start GG, flow 1 | 26.1–26.677911233 | 177.911233 ms |

Each listed socket has one restoration deferral and no recorded missed deadline. All second intervals and all join10 intervals restore at the requested end. Different protection duration is part of the measured behavior. We have not established that it causes the later delivery-share differences.

**Finite-horizon metric caution:** same-start GG's wire unique payload union is 194,580 bytes larger than its ordered app delivery. Compared with DD, GG's app sum is 193,200 bytes lower while its wire-unique sum is 1,380 bytes higher. Pre-processing receiver wire observations do not prove application acceptance. Do not call the app deficit a proven decline in network transmission efficiency; terminal gaps/buffering/discards have not been causally audited. These values are retained in each flow's `counts`.

## Reproduction, provenance, and size

[`reproduction.json`](assets/cubic-competing-20261010/reproduction.json) records **one representative `same-start-gd` replay on a separate fresh official ns-3 volume**. The patch, binary, runner, generated settings, 15 measurement/legacy CSV hashes, full-analysis hash, metrics, connections, and guard checks match. The only CSV difference is `logs_ns3/timing_results.csv`, whose wall-clock stage durations naturally differ. Both hashes are disclosed. `basic-simulation.cc:58–63,327–328` obtains `system_clock` timestamps and writes their differences. This file is excluded from *measurement* equality, not deleted or described as byte-identical. The other seven cases passed validations but were not replayed on the second volume.

- Canonical patch SHA-256: `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`.
- Binary SHA-256: `de9f678113c37a72df7e3215e876f18945c0ccecf9123f60fc8f655f9d9a6eab`.
- Runner revision: `95c306dd9fc1d6c09f9d5ebccfc27215f8c41a24`; exact runner/analyzer/exporter hashes are recorded separately. The exporter received stricter guard/data-RETX validation after that initial commit; it does not alter simulation inputs.
- Original cases took **17.4–21.6 s each**, totaling **158.3 s of case wall times**, on this machine; seven were dispatched with two workers after the first baseline check. Replay took 22.1 s. Compilation and analysis are additional work; allow several minutes for a sequential reproduction.
- The eight original cases' raw CSVs total **467,756,589 bytes** and remain local. Shared evidence is about **0.25 MB**, including settings, hashes, compact results, and one-second bins. No large traces are committed.

Run from the repository root in PowerShell. The following uses **new** names and regenerates output under `/tmp`, leaving committed evidence available for comparison. A container/volume name already used for another experiment should be changed before starting a fresh replay.

```powershell
$repoRoot = (Resolve-Path .).Path
$competingImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
docker run -d --name competing-check --mount "type=bind,source=$repoRoot,target=/work" --mount 'type=volume,source=competing-check-ns3,target=/home/ubuntu/ns-3.48' $competingImage sleep infinity
docker exec -w /home/ubuntu/ns-3.48 competing-check bash -lc 'git apply --check /work/code/kim-study/ns3.patch && git apply /work/code/kim-study/ns3.patch && ./ns3 build -j 4'

foreach ($flowMode in 'DD','GD','DG','GG') {
  $sameCase = 'same-start-' + $flowMode.ToLower()
  $joinCase = 'join10-' + $flowMode.ToLower()
  docker exec competing-check python3 /work/code/competing-flows/run_competing.py $sameCase --mode $flowMode
  docker exec competing-check python3 /work/code/competing-flows/run_competing.py $joinCase --mode $flowMode --start1-s 10
}

docker exec competing-check python3 /work/code/competing-flows/summarize_competing.py --cases same-start-dd same-start-gd same-start-dg same-start-gg join10-dd join10-gd join10-dg join10-gg --analyzer /work/code/kim-study/analyze_study.py --path-truth /work/code/kim-study/path_truth_200s.csv --out /tmp/competing-export
New-Item -ItemType Directory -Force -Path ./runs | Out-Null
docker cp competing-check:/tmp/competing-export ./runs/competing-replay
```

The original container retains raw data at `/tmp/cs30401-competing/<case>/logs_ns3`. The representative replay container is `lab1-competing-replay-20261010`, volume `cs30401-competing-replay-ns3-20261010`. These local paths are not remote archives. Reproduction does not require our retained volumes. The current checkout's revision may differ from the original runner commit; compare actual script/settings/trace hashes and metrics, rather than expecting wall time or manifest creation timestamps to match.

## What this supports, and what remains open

**Supported:** on this same-route two-CUBIC configuration, the aggregate delivery effect is small and delivery allocation depends on the guarded socket and start history. A single-flow gain is insufficient evidence of harmless coexistence. Both improvements and costs must be reported.

**Open:** exact packet-level causes of the long-run allocation changes, the unique congestion location, why late-only guard has no displayed effect, and the end-of-run wire/app gap. Scheduler-order sensitivity was controlled through role swaps; scheduler order has not been established as the cause. We did not test independent seeds, other paths/RTTs, other controllers, background traffic distributions, or more start offsets. The patch/model does not implement RACK-TLP, variable capacity, wireless errors, or hard-handover outage, and no deployed Starlink benefit is inferred.
