# CUBIC reordering guard: competing flows

**Status: in progress.** kim-seongchan with AI assistance, 2026-10-10. Based on merged `main` **b60e8e0**. This is an independent follow-up, not a team-approved topic. The [literature/context PR #11](https://github.com/Jeongmin07/CS30401-Lab1/pull/11) motivates the comparison. [Jeongmin07's Draft PR #10](https://github.com/Jeongmin07/CS30401-Lab1/pull/10) investigates the q75 deficit/K4/later-event/genuine-loss question; those controls are not repeated here.

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

## Results and limitations

No simulation results are claimed in this initial record. Successful and harmful cases, exact commands/runtime, input hashes, and reproduction results will be added after the declared comparisons run. The patch/model does not implement RACK-TLP, variable capacity, wireless errors, or hard-handover outage, and no deployed Starlink benefit will be inferred.
