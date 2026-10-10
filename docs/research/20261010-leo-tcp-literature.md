# LEO TCP literature: mechanisms, methods, and limits

Prepared by kim-seongchan with AI assistance, **2026-10-10**. This is a source-reading note, not a new experiment or a team-approved topic. Read the [context and handoff](20261010-context-and-handoff.md) alongside it. The earlier, narrower [related-work note](../../code/kim-study/RELATED_WORK_NOTE.md) remains the reference for the implemented guard and its completed controls.

## How to use this review

The useful contribution is not to copy a paper's network parameters or claim that reordering tolerance is new. Separate three questions: **what changes in the network, what the TCP implementation infers, and what the proposed intervention costs**. The current course model contains changing ISL paths and propagation delay, but no default handover outage, random wireless loss, or varying link capacity. Real access-network measurements and emulators with explicit link teardown therefore need a model translation before becoming experiment conditions here. See the [course model reference](../LAB_REFERENCE.md).

The ten paper entries below were read in the linked primary-source versions. “Borrow” and “Fit” are our assessment, not conclusions claimed by the authors. Section/figure locators refer to those versions. An arXiv version is identified explicitly; publication and implementation details should not be inferred from an unverified later version.

| Reading purpose | Start with | Relevance to this repository |
| --- | --- | --- |
| Route changes and packet overtaking | [P1](#p1-hypatia), [P2](#p2-end-to-end-delivery-and-reordering), [P3](#p3-stability-first-routing) | Motivate causal packet analysis and the delay/stability tradeoff |
| Why a larger loss threshold can hurt | [S1](#s1-tcp-ncr-rfc-4653), [S2](#s2-rack-tlp-rfc-8985), [S3](#s3-early-retransmit-rfc-5827) | Explain feedback starvation and distinguish our prototype from established algorithms |
| Information needed by a route-aware controller | [P4](#p4-satcp), [P5](#p5-satpipe), [P8](#p8-orbcc) | Make notification, timing, and telemetry assumptions explicit |
| Stronger evaluation | [P6](#p6-tcp-congestion-control-performance-over-starlink), [P7](#p7-a-first-look-at-starlink-performance), [P9](#p9-emulation-versus-simulation) | Separate transient/whole-run metrics, competition, and implementation fidelity |
| An alternative delay-based question | [P10](#p10-tcp-vegas-a) | Diagnose propagation delay versus queueing before modifying Vegas |

## Papers read

### P1. Hypatia

**Simon Kassing, Debopam Bhattacherjee, André Baptista Águas, Jens Eirik Saethre, Ankit Singla.** “Exploring the ‘Internet from space’ with Hypatia.” ACM IMC 2020, pp. 214–229. [Author PDF](https://bdebopam.github.io/papers/imc2020-hypatia.pdf), [DOI](https://doi.org/10.1145/3419394.3423635), [code](https://github.com/snkas/hypatia).

- **Read:** §4.2, Figs. 4–5. Packet-level NewReno/Vegas experiments include a single 10-Mbit/s flow and 100-packet queue. A shorter route lets later packets overtake earlier ones; delay increases also confuse a delay-based controller.
- **Borrow:** align route/propagation delay, TCP state, and receiver delivery; then identify the particular packets and ACKs causing recovery.
- **Fit:** strong motivation for our problem, not validation of our CUBIC guard. Its constellations, paths, and original ns-3 code differ from the course port. A visually similar cwnd dip alone is insufficient evidence of spurious loss detection.

### P2. End-to-end delivery and reordering

**Rasmus Sibbern Frederiksen, Thomas Gundgaard Mulvad, Israel Leyva-Mayorga, Tatiana Kozlova Madsen, Federico Chiariotti.** “End-to-End Delivery in LEO Mega-constellations and the Reordering Problem.” Reviewed [arXiv:2405.07627v1, 2024](https://arxiv.org/html/2405.07627v1); this version describes a PIMRC Workshops submission.

- **Read:** §III–IV, Table I. A [netem-based emulator](https://github.com/rasmussibbern88/satellite_tcp_emulator) uses a OneWeb-like 1,200-km constellation, 100-Mbit/s links, 1,000-second runs, 15-second L2 and 30-second L3 updates. Goodput is sampled at 20 Hz; topology and city pair are varied.
- **Borrow:** compare short delivery interruptions with whole-run averages and check a second geometry. Similar long-run performance can conceal different transient behavior.
- **Fit:** a useful evaluation pattern, not a parameter prescription. Its emulated stack, endpoint arrangement, constellation, and update cadence differ from our 100-ms course routing. Do not carry broad statements about TCP's reordering limits over to every modern loss detector.

### P3. Stability-first routing

**Gregory Stock, Juan A. Fraire, Santiago Henn, Holger Hermanns, Andreas Schmidt.** “A Stability-first Approach to Running TCP over Starlink.” Reviewed [arXiv:2408.07460v1, 2024](https://arxiv.org/html/2408.07460v1).

- **Read:** §III–IV-A. Compare shortest-delay routes with routes retained for stability. The artCP evaluation abstracts congestion-window evolution using RTT/reordering events rather than individual packets; senders are always backlogged and receiver capacity is unlimited.
- **Borrow:** distinguish all route changes from delay-decreasing changes likely to reorder packets. A routing alternative would trade added path delay against fewer disruptive transitions.
- **Fit:** helps formulate an alternative question or classify existing events. It cannot establish packet-level CUBIC/SACK/PRR behavior or finite-transfer completion times. Implementing new forwarding policies is a separate project, not a small change to the current guard.

### P4. SaTCP

**Xuyang Cao, Xinyu Zhang.** “SaTCP: Link-Layer Informed TCP Adaptation for Highly Dynamic LEO Satellite Networks.” IEEE INFOCOM 2023, pp. 1–10. [Author PDF](https://xyzhang.ucsd.edu/papers/Xuyang.Cao_INFOCOM23_SaTCP.pdf), [DOI](https://doi.org/10.1109/INFOCOM53939.2023.10228914), [LeoEM code](https://github.com/XuyangCaoUCSD/LeoEM).

- **Read:** §III-C, IV–VI, Algorithm 1, Tables I–II. A Starlink measurement motivates the design; the main evaluation uses Mininet/Linux LeoEM, 150-Mbit/s links, a 1,000-packet queue, six city pairs, and explicit disruption. Link-layer reports support temporarily suppressing CUBIC window reduction/timeout reset.
- **Borrow:** report-timing error versus protection duration; transient and whole-run results; coexistence with unchanged CUBIC.
- **Fit:** closest comparison for *information assumptions*, not the same patch. Our controller changes the loss threshold. SaTCP's disruption/BP results cannot predict gains in the course's instantaneous ISL transitions; coexistence results also do not show universally equal sharing.

### P5. SatPipe

**Ding Zhao, Xinyu Zhang, Myungjin Lee.** “SatPipe: Deterministic TCP Adaptation for Highly Dynamic LEO Satellite Networks.” IEEE INFOCOM 2025, pp. 1–10. [Author PDF](https://xyzhang.ucsd.edu/papers/Ding.Zhao_INFOCOM25_SatPipe.pdf), [DOI](https://doi.org/10.1109/INFOCOM55648.2025.11044600), [code](https://github.com/dzhao99/SatPipe).

- **Read:** §III–V, Algorithm 2, Figs. 8–20. Timing from synchronization/initial delay measurements drives queue maintenance followed by propagation-RTT remeasurement in a Linux BBR patch. Evaluation uses a Gen-2 Starlink client in San Diego, six AWS locations, Linux 6.8.10, and multiple three-minute iperf3 runs, plus application/competition tests.
- **Borrow:** report goodput, low-throughput percentiles, RTT, and retransmission together; test flow joins/leaves rather than only a permanent single flow.
- **Fit:** evaluation ideas transfer more readily than the implementation. Porting BBR states and access-outage behavior is substantial work; real-network gains are not expected gains for our default ISL model.

### P6. TCP congestion control performance over Starlink

**Johan Garcia, Simon Sundberg, Anna Brunstrom.** “TCP Congestion Control Performance over Starlink.” ANRW 2025, pp. 70–77. [University PDF](https://www.diva-portal.org/smash/get/diva2%3A1992495/FULLTEXT01.pdf), [DOI](https://doi.org/10.1145/3744200.3744760).

- **Read:** §3–7, Figs. 4–5. Rooftop Gen-2 measurements compare 14 Linux controllers using 180-second runs, one/ten parallel flows, and randomized replication blocks. BBRv3 uses a separately patched kernel. Startup and competition matter alongside averages.
- **Borrow:** separate startup/steady state and change competitor start order. **§6 completion curves measure time from SYNACK to byte prefixes of long-flow captures**; they are not separate finite transfers at each size. Label that method if reused; our finite-flow controls actually terminate at their declared size.
- **Fit:** queue size was not a controlled course parameter. Real capacity/scheduling variability differs from our deterministic model; its repeated measurement blocks do not justify treating identical ns-3 reruns as independent samples.

### P7. A first look at Starlink performance

**François Michel, Martino Trevisan, Danilo Giordano, Olivier Bonaventure.** “A First Look at Starlink Performance.” ACM IMC 2022, pp. 130–136. [Accepted manuscript](https://iris.polito.it/retrieve/bb117d3d-877f-4116-953f-5f80f1f5cc79/Starlink_characterization.pdf), [DOI](https://doi.org/10.1145/3517745.3561416). The repository cover precedes the manuscript.

- **Read:** §2–3, Table 2, Figs. 3–4. Belgium measurements compare idle/light/heavy load, upload/download, RTT distributions, and loss bursts. Loads include 100-MB HTTP/3 bulk and two-minute light QUIC traffic.
- **Borrow:** distinguish propagation delay from load-induced delay; examine loss duration/burst structure and direction instead of an overall loss percentage alone.
- **Fit:** the authors infer that ISLs were inactive in their observed deployment. This is not a direct measurement of our ISL topology. Observed loss mixes possible causes; inserting that percentage as independent random wireless errors, or equating QUIC loss with TCP retransmission counts, would need separate justification.

### P8. OrbCC

**Aiden Valentine, Ian Wakeman, George Parisis.** “OrbCC: High-Throughput and Low-Latency Data Transport for LEO Satellite Networks.” Reviewed [arXiv:2508.19067v2, 2026-03-25](https://arxiv.org/html/2508.19067v2). Version 1 used the title “LeoTCP”; count these as versions of one work, not independent papers.

- **Read:** §III and evaluation sections. OMNeT++/INET experiments use path/per-hop information, a Starlink-like shell, 100-ms route updates, and BDP-based buffers; default configurations use five runs. Evaluation includes flows with different RTTs and changing shared bottlenecks, with Linux comparison.
- **Borrow:** include delay and Jain fairness alongside delivered bytes; document queue size relative to BDP and confirm that tested flows really share a bottleneck.
- **Fit:** useful evaluation design. Its telemetry and transport machinery are not available to an ordinary endpoint in our model. Adding that support and porting the controller would be a separate implementation, not a guard baseline already present here.

### P9. Emulation versus simulation

**Aiden Valentine, Mihai Mazilu, James Knowles, Ian Wakeman, George Parisis.** “Emulation vs Simulation: A Case Study from Congestion Control Algorithms in Low Earth Orbit Satellite Networks.” Reviewed [arXiv:2608.02095v1, 2026-08-03](https://arxiv.org/html/2608.02095v1). The arXiv comments name MASCOTS 2026; publisher proceedings were not independently checked for this note.

- **Read:** §III, IV-A/IV-D. Compare OMNeT++ 6.4.0/INET 4.6.0 against Mininet/Linux, with incremental SACK, pacing, and RACK support. Controlled changes isolate capacity, delay, and loss; telemetry uses different sampling intervals.
- **Borrow:** record recovery/pacing/SACK/version features and change one mechanism at a time before comparing controllers. Align metric definitions and sampling intervals across implementations.
- **Fit:** a warning against interpreting a controller name as an identical complete TCP stack. The paper's ns-3 availability discussion concerns version 3.45; evidence about our course 3.48 must come from its actual source. This is methodology, not a validation or refutation of our patch.

### P10. TCP Vegas-A

**K. N. Srijith, Lillykutty Jacob, A. L. Ananda.** “TCP Vegas-A: Improving the Performance of TCP Vegas.” Computer Communications 28(4), 2005, pp. 429–440. [Author PDF](https://srijith.net/vu/publications/journals/TCP_Vegas-A_COMCOM05.pdf), [DOI](https://doi.org/10.1016/j.comcom.2004.08.016).

- **Read:** §2.2, §4.1, §5.3. Explain why a changed propagation RTT can invalidate Vegas's old base RTT; evaluate adaptive alpha/beta, including an NS-2 delay-step control and an Iridium example.
- **Borrow:** separate a propagation-delay step from a queueing-only control before diagnosing the exploratory Vegas result.
- **Fit:** Vegas-A adapts thresholds; it is not simply a base-RTT reset. The old example's 20→200-ms jump, topology, and Vegas parameters are not course defaults. Our 100-Mbit/s baseline alone does not establish this failure mechanism. Treat this as an alternative hypothesis if the team chooses to investigate Vegas.

## Loss-recovery standards

### S1. TCP-NCR, RFC 4653

**S. Bhandarkar, A. L. N. Reddy, M. Allman, E. Blanton.** “Improving the Robustness of TCP to Non-Congestion Events.” Experimental, August 2006. [RFC 4653](https://www.rfc-editor.org/rfc/rfc4653.html), §2–3/5.

NCR combines a state-dependent threshold with Extended Limited Transmit. Increasing tolerance delays genuine-loss repair, and a finite flight may not produce enough feedback to meet a large threshold. Our scheduled fixed K and known-size exemption are **not an NCR implementation**. Use this to explain the measured cost, not to claim that raising K is a new principle.

### S2. RACK-TLP, RFC 8985

**Y. Cheng, N. Cardwell, N. Dukkipati, P. Jha.** “The RACK-TLP Loss Detection Algorithm for TCP.” Standards Track, February 2021. [RFC 8985](https://www.rfc-editor.org/rfc/rfc8985.html), §3 and §9.3.

RACK uses transmission time and ACK/SACK evidence with a reordering allowance/timer. TLP can obtain missing feedback with a probe. Loss detection is distinct from the congestion-control growth rule. A timer that only restores our K does not implement either algorithm or itself promise immediate repair. No RACK-TLP baseline was implemented in this study, so deployed Linux superiority claims are unsupported.

### S3. Early Retransmit, RFC 5827

**M. Allman, K. Avrachenkov, U. Ayesta, J. Blanton, P. Hurtig.** “Early Retransmit for TCP and Stream Control Transmission Protocol (SCTP).” Experimental, April 2010. [RFC 5827](https://www.rfc-editor.org/rfc/rfc5827.html), §1/3/4.2.

Very small flights may not supply three duplicate ACKs. Early Retransmit conditionally lowers the threshold when no new data is available, at a cost in reordering tolerance. It motivates tiny-flight and true last-packet-loss controls. The current exemption preserves the original detector; it neither implements Early Retransmit nor fixes all baseline timeouts.

## Discovery lead: not a completed full-paper review

**Zeqi Lai, Zonglun Li, Qian Wu, Hewu Li, Jihao Li, Xin Xie, Yuanjie Li, Jun Liu, Jianping Wu.** “LeoCC: Making Internet Congestion Control Robust to LEO Satellite Dynamics.” ACM SIGCOMM 2025, pp. 129–146. [DOI](https://doi.org/10.1145/3718958.3750491), [official program/abstract](https://conferences.sigcomm.org/sigcomm/2025/program/papers-info/), [author repository and replay traces](https://github.com/SpaceNetLab/LeoCC).

The official abstract describes detecting network reconfiguration and resetting a model. The repository provides measured traces and replay support. We verified those sources, **not the full paper's experiment conditions**; do not cite an unverified result or call this an implemented comparator. It is a promising next read for endpoint information and trace-driven evaluation.

## Proposed use in the assignment

These are suggestions based on the review, not completed tests or new team rules:

1. **Position the existing study honestly.** Established work motivates reordering robustness. Our narrower evidence concerns one supplied CUBIC/SACK/PRR implementation, externally scheduled activation, and loss-recovery tradeoffs. Both local benefit and whole-run harm belong in the report.
2. **Close a causal gap before a large sweep.** The q75 experiment already supplies a negative result. Packet identity, drop location, ACK evidence, congestion state, and accumulated receiver-byte differences can explain more than another average-throughput table.
3. **Add one discriminating comparison if time allows.** Competing guarded/default flows, a second geometry, or broader K8 finite-flow coverage answer different questions. Choose one, control its inputs, and include a failure case. Our current offset sweep already tests shifted schedules; repeating it is not a new notification mechanism.
4. **State information costs.** The schedule uses known simulation events; the exemption needs known total transfer size. Obtaining reliable advance notice, telemetry, or remaining-flight information at a real endpoint remains unimplemented.
5. **Avoid a deadline-driven full protocol port.** RACK, SaTCP, SatPipe, and OrbCC are useful comparison designs, but a partial port without its dependencies could create a misleading baseline. A clearly bounded course study with causal evidence is the lower-risk submission path.

## Where to find and verify more material

- Search terms that target mechanisms: `LEO TCP packet reordering route change`, `satellite congestion control handover`, `TCP non-congestion loss RACK`, `LEO emulation simulation pacing SACK`, and `Vegas propagation delay rerouting`.
- Use author/university PDFs, DOI publisher records, numbered arXiv versions, official conference programs, RFC Editor, and author repositories. A discovery search or abstract is a lead, not evidence for an unseen experiment table.
- Keep a paper's exact version, section/figure, controller **and** recovery stack, topology/access model, queue, load, duration, and metric definition. Record missing settings as unknown instead of filling them from another paper.
- Read the method, figure caption, limitations, and code version before borrowing a condition. Cite the source and explain why the changed condition isolates a question in the course model. Changing a number alone does not establish a useful research contribution.
