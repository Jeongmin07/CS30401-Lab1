# Screening alternative LEO TCP research topics

**Status: screening completed; candidate fix not implemented or evaluated, 2026-10-10.** Owner: kim-seongchan with AI assistance. [PR13](https://github.com/Jeongmin07/CS30401-Lab1/pull/13) starts from `main` at `b60e8e019053c7d33b853510ec06c3d94ee78faf`. The user requested a different topic after K8/K20 competition evidence did not support adopting that policy. Existing PR10/11/12, results and branches are preserved. This proposal does not change `docs/PLAN.md` or assign work to teammates.

## Recommendation and evidence boundary

First investigate **Vegas confusing an increase in propagation delay with congestion**. A fresh supplied-state run exhibits substantial degradation. A matched synthetic pair reproduces a persistent reduction caused by channel delay increasing without drops. The next question is whether renewing Vegas's RTT reference can recover delivery **without absorbing real queue delay or harming competing flows**. No improvement has been tested here. This mechanism and reference-renewal ideas are prior work, not a new invention.

| Priority | Research question | Evidence now | Gate before final selection |
| --- | --- | --- | --- |
| 1 | Vegas RTT-reference adaptation after a longer LEO path | Fresh LEO baseline and matched delay-only pair below | Trace internal decisions; evaluate bounded renewal under propagation and real congestion controls |
| 2 | Queue management/flow isolation for short TCP alongside bulk | CoDel/FQ-CoDel exist in ns-3.48; no new pilot | Measure actual queue/FCT cost; compare matched FIFO/CoDel/FQ-CoDel buffering |
| 3 | Bounded tail-loss probe for finite flows | Prior synthetic tail-loss diagnostics show about 1.1 s extra FCT | Establish occurrence under course-model queue loss; preserve congestion reaction and bound redundant traffic |
| 4 | CUBIC pacing for bursts and short-flow delay | Existing pacing controls; no new pilot | Show burst-to-queue/drop causality and test paced/unpaced competition |
| 5 | BBR RTT exploration cost | Old sender summaries already about 93.4–94.5 Mbps at 100 Mbps | Measure ProbeRTT/queue costs before seeking a small remaining throughput gain |

## Fresh observations

All three runs use ordinary `TcpVegas`, 100-Mbps links, q100 device DropTail queues, 1,380-byte MSS, one effectively infinite transfer and **empty TCP parameter strings**. The existing patch supplies instrumentation, but no K8/K20 guard is enabled. Each completed with exit code zero. Below, goodput is ordered receiver application bytes divided by the specified elapsed window, not sender ACK totals or link utilization percentages.

### Matched synthetic delay contrast

This two-node diagnostic is not the LEO simulation. Rate, buffering, application, TCP and startup match; channel propagation changes at 5 seconds and no loss is injected. The micro driver specifies initial ssthresh 900 MSS and uses ns-3 default RNG settings; the LEO config explicitly sets seed 123456789. Do not compare absolute rates across these topologies as matched results.

| Observation | Fixed propagation | Increased propagation |
| --- | --- | --- |
| Run ID | `topic-vegas-fixed90ms` | `topic-vegas-step90to97ms` |
| Actual pure propagation RTT | 90 ms | 90 to **96 ms** at 5 s |
| App goodput, 15–20 s | 26.306112 Mbps | 6.659328 Mbps |
| Final cwnd | 241 MSS | 58 MSS |
| Traced drops / data retransmissions / recovery entries | 0 / 0 / 0 | 0 / 0 / 0 |
| App bytes, entire 20 s | 39,456,960 | 16,001,100 |
| Runner wall time | 0.567 s | 0.211 s |

Late-window delivery decreases about **74.7%**. Before 5 s, cwnd, held SRTT, sender data/ACK and receiver-app records match exactly (66, 1,196, 3,672 and 2,397 rows). After the step, only the changed-delay case decreases from 74 to 58 MSS and stays at 58 from 6.790946080 s to run end. Startup histories therefore do not explain this contrast. Still, the fixed case also exits slow start early and increases slowly; startup is a separate limitation, and whole-run averages are not the main causal metric.

**Setting discrepancy:** the changed-delay run was named for 90 to 97 ms and requested one-way `after_ms=48.5`. Retained `scratch/study_micro/study_micro.cc:73,94` passes a double to `MilliSeconds`; the integer overload in `src/core/model/nstime.h:1290–1292` truncates it to 48 ms. Actual one-way delay is 45 to 48 ms. Late tagged packet records show minimum forward delay 48.114720 ms including serialization. Original names/manifests/logs are preserved; do not describe this as a 7-ms experiment. Future diagnostics must use integer settings or explicitly fix fractional-time handling and export a different patch.

### Supplied Seoul–London dynamic baseline

`topic-vegas-q100-100m-dynamic` uses the official supplied 200-second state, nodes 1584→1585, 100-ms forwarding updates, seed 123456789, pacing off and a 100-GB transfer starting at zero. It delivered **1,037,783,460 app bytes = 41.5113384 Mbps** over 200 seconds; runner wall time was 90.447 s. Traced drops were zero; data retransmissions were 41 with two recovery entries.

| Receiver app window [start, end), seconds | Goodput, Mbps |
| --- | ---: |
| 111.6–121.6 | 96.230160 |
| 131.6–141.6 | 50.241936 |
| 150–160 | 26.091936 |
| 177.4–187.4 | 13.234752 |
| 190–200 | 4.996704 |

The supplied path-truth trace spans propagation RTT 87.454–98.535 ms, with upward steps about 3.061 ms at 121.6 s and 7.231 ms at 187.4 s. Continued cwnd reduction is consistent with a stale reference. **Immediate reduction at 121.6 s also overlaps reordering recovery**, so it cannot all be attributed to the estimator. Actual internal reference/decision variables are not traced yet. SRTT is a held smoothed sender estimate, not pure path delay or a directly measured internal reference.

Windows were selected during diagnosis, not preregistered; they are not independent statistical samples. Each condition was run once in a retained patched volume. No fresh-volume replay or statistical repetition is claimed.

## Mechanism and primary reading

Actual ns-3.48 `TcpVegas::PktsAcked` keeps `m_baseRtt` as a lifetime minimum and `m_minRtt` as a cycle minimum. Re-enabling and cycle completion reset the latter, without raising the lifetime minimum. `IncreaseWindow` computes `diff = w - floor(w * baseRtt / minRtt)` and reduces cwnd by one MSS per cycle above beta. A permanently longer path can look like a persistent queue. This source-backed explanation fits the pilots; direct state tracing remains necessary. [Versioned Vegas source](https://raw.githubusercontent.com/nsnam/ns-3-dev-git/ns-3.48/src/internet/model/tcp-vegas.cc)

The ns-3.48 socket supplies **SRTT** to `PktsAcked`, including Vegas, rather than unsmoothed RTT. Keep that input unchanged in the first renewal experiment to isolate the change. [Versioned socket source](https://raw.githubusercontent.com/nsnam/ns-3-dev-git/ns-3.48/src/internet/model/tcp-socket-base.cc)

1. **La, Walrand and Anantharam, _Issues in TCP Vegas_ (1999), §§3–4.** Studies longer-route failure, sustained-minimum reference renewal and persistent-congestion pitfalls. It provides a design lead and a required counterexample. Its much larger delay changes are not automatically suitable course parameters. [Berkeley report](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1999/Archive/ERL-99-3.pdf)
2. **Gu and Zhang, _Behavior and performance improvement of TCP Vegas in LEO satellite networks_ (WCNM 2005), pp. 891–894, DOI 10.1109/WCNM.2005.1544194.** The institutional abstract links longer LEO paths with mistaken window reduction. Only the abstract/publication record was available; the exact algorithm and experimental settings were **not** read or reproduced. [Publication record](https://pure.bit.edu.cn/en/publications/behavior-and-performance-improvement-of-tcp-vegas-in-leo-satellit/)
3. **Bhosale et al., _A Characterization of Route Variability in LEO Satellite Networks_ (PAM 2023), §§3–4/Table 2.** Supports route/RTT variability and utilization–delay tradeoffs. It feeds Hypatia-derived delays into Mahimahi/Pantheon, rather than the course packet-level simulator; its TCP measurements cannot replace ours. [Author paper](https://saeed.github.io/files/leo_study_pam2023.pdf)

## Next experiments before claiming a solution

1. **Observe the internal mechanism:** add opt-in base RTT, cycle minimum, sample count, diff and decision/renewal traces. Confirm tracing leaves baseline outputs unchanged. Keep SRTT input, startup, loss recovery and K3 fixed.
2. **Bound reference-correction benefit:** an exact-route-timing reset is a diagnostic oracle/upper bound, not a deployable solution. If useful, an operational notification needs a sender-delivery mechanism, timing accuracy and latency. TCP cannot obtain future path truth for free.
3. **Implement one bounded practical renewal method:** endpoint-only recent-minimum/re-measurement may absorb standing queues; notification-based renewal has information costs and still needs clean sampling after old-path packets leave. Do not simultaneously change startup/raw RTT input.
4. **Reject congestion-blind changes:** compare original/candidate under fixed propagation, increased propagation without congestion, and sustained real congestion with fixed/changing propagation. Measure app delivery, queue residence, retransmissions, renewal frequency and competitor service. Keep buffering/traffic equal. Reject a method that simply ignores congestion.
5. **Validate in the course model:** supplied LEO state, a smaller queue/another justified load, and competition. Compute original/candidate metrics identically. Apply the exported final patch in a fresh official volume before final reproducibility claims.

Retain this topic only if receiver delivery improves materially and queue/competition costs are explainable and bounded. If practical assumptions are too strong, move to queue-delay/FCT rather than tuning many arbitrary thresholds. The team still needs to agree on a final topic and produce the English report/submission.

## Secondary candidates

**Queue management:** bulk plus 20/80-MSS short flows, FIFO/CoDel/FQ-CoDel at the same measured dominant egress, initially source GSL if warranted. Use equal device buffering, e.g. root98+device2 in every arm; an extra q100 below AQM hides its queue. Include short-flow-only controls and actual residence/FCT. No new pilot has established a cost or a satellite-specific cause yet. [FQ-CoDel, RFC 8290](https://www.rfc-editor.org/rfc/rfc8290.html), [CoDel, RFC 8289](https://www.rfc-editor.org/rfc/rfc8289.html)

**Tail-loss probe:** [prior phase-2 diagnostics](../../code/kim-study/PHASE2_NOTE.md) show large FCT costs under deliberately injected loss, not its natural default-model frequency. A bounded sender probe needs ACK cancellation, limited probes, RTO fallback and proper congestion response. Full RACK-TLP is too broad for this screening. [RFC 8985 §7](https://www.rfc-editor.org/rfc/rfc8985.html), [Flach et al., SIGCOMM 2013](https://research.google/pubs/reducing-web-latency-the-virtue-of-gentle-aggression/)

**Pacing:** existing ns-3 controls make a small contrast feasible, but mixed-flow evaluation matters because adverse synchronization/competition cases are known. No new pacing run was executed. [ns-3.48 controls](https://raw.githubusercontent.com/nsnam/ns-3-dev-git/ns-3.48/src/internet/model/tcp-socket-state.cc), [Aggarwal, Savage and Anderson, INFOCOM 2000](https://cseweb.ucsd.edu/~savage/papers/Infocom2000pacing.pdf)

**BBR:** ns-3.48 is a BBRv1-family model validated against Linux5.4, not BBRv3. It has a 10-s minimum-RTT window, a 200-ms ProbeRTT minimum and roughly 2-BDP cwnd target. Old q100/q1000 sender ACKed summaries are 93.4291/94.4857 Mbps, not newly validated app metrics. A four-case default/long-window diagnostic could bound exploration cost, but disabling ProbeRTT is not a final improvement. [Versioned documentation](https://raw.githubusercontent.com/nsnam/ns-3-dev-git/ns-3.48/src/internet/doc/tcp.rst), [model](https://raw.githubusercontent.com/nsnam/ns-3-dev-git/ns-3.48/src/internet/model/tcp-bbr.cc), [BBR design §4.3.5](https://datatracker.ietf.org/doc/html/draft-cardwell-iccrg-bbr-congestion-control-00#section-4.3.5)

SatPipe's handover-freeze mechanism is a poor direct fit because the default course model has no outage. This is a scope/model decision, not a claim that proposal is ineffective. [SatPipe author paper](https://xyzhang.ucsd.edu/papers/Ding.Zhao_INFOCOM25_SatPipe.pdf)

## Reproduction and original access

Run source at launch: **`76885d178cd28838e9d4f97a23836cffb3cde7fc`**. Original runner did not save Git commit; operator-read launch HEAD supplements it here without rewriting `case.json`. The exporter was added after simulation and independently checks app totals/input hashes. [Commands/exporter](../../code/topic-screening/README.md), [small table](../../code/topic-screening/evidence/results.csv).

| Identity | Exact value |
| --- | --- |
| Official image | `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1` |
| Host-inspected digest | `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4` |
| Canonical patch SHA-256 | `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245` |
| LEO binary SHA-256 | `de9f678113c37a72df7e3215e876f18945c0ccecf9123f60fc8f655f9d9a6eab` |
| Micro binary SHA-256 | `6cd406069c283831b051c1d728e03804954e6638267b85f600b1ac5851ce2448` |
| LEO config SHA-256 | `0eb9191f06cdf549eb1d13947203ab2acd329112c97f5b7c550eeb52b4affe5b` |
| LEO schedule SHA-256 | `e6cde3aa7716856e46d24c3833354df90407313ece13a5ffbd1b789fa4fea23c` |

Complete originals/full analysis: [43,431,562-byte archive](https://github.com/Jeongmin07/CS30401-Lab1/releases/download/leo-topic-screening-20261010/cs30401-topic-raw-20261010.tar.gz), SHA-256 **`39e45da2a0405bccc6e439debd947517634821cec2ab906451d56a669ced5f18`**. All 45 original-file hashes were checked against archive streams, host-copy hash matched, and GitHub asset size/digest matched. [Release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/leo-topic-screening-20261010). Raw CSV and full analysis are not duplicated in Git.

## Questions for teammates

Three humans use separate AI chats on separate laptops; this is one teammate's proposal, not a central assignment. At the starting check PR10/11/12 were open, with no open Issues. This branch preserves those investigations. Internal AI reviews do not constitute teammate approval.

Assess whether the delay-only contrast supports the hypothesis, whether real-congestion controls are adequate, whether notification/re-measurement assumptions meet the assignment, and whether queue-delay/FCT is a better final topic. No fixed prompt or role is required. Read PR13's branch, not just `main`: candidate improvement, final team choice, report and submission remain outstanding.
