# CUBIC HyStart during a supplied LEO route transition

**Status: six declared cases completed successfully, 12 October 2026.** The conditions and candidate window below were written before execution. This is an independent diagnostic by kim-seongchan with AI assistance, not a team topic decision. Existing BBR/forecast-loss containers and other experiments are untouched.

## Question and declared conditions

Does the supplied CUBIC HyStart leave slow start in a way that harms a finite flow spanning the natural 121.6-second Seoul–London route change? A source-level threshold argument alone will not answer this question: actual HyStart on/off runs, the exit branch, ordered application delivery and drops will be checked.

Use the pinned official course image `ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`, a new container `lab1-orbit-hystart-20261012`, and a new volume `cs30401-orbit-hystart-ns3-20261012`. Limit the container to two CPUs and 4 GiB; compile with **one** job while the other tracks run concurrently. Apply canonical v6 instrumentation and passive HyStart reason logging, then export one combined patch for replay. No threshold guard, outage, random radio loss, varying capacity or new constellation state is introduced.

The initial pair uses one CUBIC flow from node 1584 to 1585, **8 MiB = 8,388,608 bytes**, start **121.2 s**, simulation end **140 s**, **100 Mbit/s** equal link rates and **1,000-packet** drop-tail queues. These are controlled course settings, not measured Starlink values. At this rate the flow's ideal serialization duration is about 0.671 s; normal startup can overlap the route change. The settings and full supplied state are identical within a pair. Preserve the original TCP MSS, initial window, buffers and HyStart thresholds, changing only the explicitly declared switch.

The provided `path_truth_200s.csv` changes propagation RTT from **87.507 ms at 121.5 s to 90.568 ms at 121.6 s**. That file supplies operator-oracle geometry/routing information, not a deployed predictor. It does not supply future queueing. ns-3.48's DELAY branch uses the minimum RTT itself as its clamped threshold, and `PktsAcked` receives SRTT; these limitations will be distinguished from the measured ACK-train branch.

## Bounded execution plan

No more than six cases; stop each incomplete/failed simulation after 240 wall-clock seconds and preserve it. The initial three cases are `near-on`, `near-off`, and `near-on-unobserved`. The last case disables the new passive HyStart and queue observers and checks the unchanged v6 measurement CSVs against `near-on`; HyStart remains enabled.

If the on/off pair differs, run `stable-on` and `stable-off` with the same 8 MiB transfer starting at **119.2 s**, where the supplied route is unchanged during expected startup, and implement one small opt-in candidate for `near-forecast`. Its only candidate action is to defer an ACK-train-only HyStart exit inside the declared oracle window **121.6–121.781136 s**, where the horizon is `2 * max(old, new propagation RTT)`. A DELAY decision remains effective, and behavior outside that window remains baseline. This is an exploratory finite-window policy, not a reason to disable HyStart globally. If the measured baseline exit is outside the forecast window, the candidate may do nothing; that negative result will be reported.

No future packet/queue trace or completion result is fed into the policy. A different start-time control is informative but does not freeze every physical variable, and will not be presented as exact per-hop route causality.

## Measurements and decision boundary

Require actual delivery of all 8 MiB before reporting completion time (`last unique application delivery - application start`, including setup). Record receiver bytes, drops by layer and tagged transmission, retransmissions, recovery/LOSS transitions, cwnd/ssthresh, actual socket CUBIC/HyStart settings, round resets, HyStart input RTT/minimum/sample count, ACK spacing and elapsed round time, and the exact exit reason bitmask. Wire Rx is a pre-TCP observation and is separate from ordered application delivery. ACK-train and DELAY may both qualify in one callback.

Every run will retain its exact command/environment, source and patch hashes, binary/library hashes, input hashes, runtime, status and raw output hashes. Compact summaries go under `assets/20261012-orbit-hystart/`; large raw traces remain in the dedicated container. Completed deterministic pairs are not statistical replications. An actual null result is a valid conclusion for these settings, and no gain is assumed before running them.

## Results

**The measured conditions do not support a harmful LEO-induced early-exit claim.** HyStart enabled completed faster and with fewer actual drops than disabled, both near the route change and in the earlier control. The narrow forecast variant performed no deferrals and reproduced the original measurements exactly. Retain stock HyStart for these settings; no blanket disabling or claimed improvement is supported.

All six cases delivered exactly **8,388,608 unique application bytes** before 140 s. Completion time includes connection establishment and is measured from the declared application start to its last ordered delivery. Source: [`results.csv`](assets/20261012-orbit-hystart/results.csv) and the validated per-case [`summaries`](assets/20261012-orbit-hystart/cases/).

| Case | Start s | Actual HyStart | Completion s | Distinct tagged drops / retx | Recovery / LOSS | Observed HyStart exit |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| near-on | 121.2 | on | 1.342252777 | 200 / 200 | 1 / 0 | ACK train at 122.096818080 s |
| near-off | 121.2 | off | 1.421403610 | 1,245 / 1,245 | 1 / 0 | disabled |
| stable-on | 119.2 | on | 1.319287791 | 223 / 223 | 1 / 0 | ACK train at 120.084492347 s |
| stable-off | 119.2 | off | 1.407567463 | 1,271 / 1,271 | 1 / 0 | disabled |
| near-on-unobserved | 121.2 | on | 1.342252777 | 200 / 200 | 1 / 0 | logger intentionally disabled |
| near-forecast | 121.2 | on, oracle window | 1.342252777 | 200 / 200 | 1 / 0 | same ACK-train exit; zero deferrals |

Disabling HyStart increases completion time **5.90% near the change** and **6.69% in the earlier control**, relative to the corresponding enabled case. These are deterministic observations of two paired operating points, not confidence intervals. Both earlier flows finish before 121.6 s, so that pair does not encounter the target route transition. It is still a different start time, rather than a frozen-topology replay of the same packets.

### What actually caused the recorded exit?

The near-on event is a real slow-start exit: `ssthresh` changes from 4,294,967,295 B to the current **2,642,700 B = 1,915 MSS**. The exact instrumented branches report **reason mask 1 (ACK train)**, with no DELAY bit. At 122.096818080 s:

| Original predicate input | Measured value |
| --- | ---: |
| ACK gap before updating `lastAck` | 0.229440 ms, below the original 2-ms limit |
| Round elapsed time | 87.416049 ms |
| Stored minimum RTT | 87.250000 ms |
| Current round minimum | 104.534163 ms |
| DELAY threshold | 87.250000 ms |
| Input SRTT | 134.669555 ms |

The ACK train qualifies because elapsed round time exceeds the stored minimum and the ACK gap meets the source predicate. DELAY does not qualify: the round minimum is below `87.25 + 87.25 = 174.5 ms`. The earlier enabled control exits through the same branch at the same 1,915-MSS window. These values are TCP RTT/round state; they are not interchangeable with the instantaneous operator propagation trace.

Actual tagged **TcDrop at the source already occurs at 122.083510648 s**, about **13.307432 ms before** near-on's exit. Queue instrumentation independently records a maximum source-device wait of **114.632774 ms**, and the tagged source's served queue visits average **65.618675 ms**. It supports substantial queue pressure rather than an isolated 3.061-ms geometry rise being mistaken for congestion. It does not reconstruct every per-hop route of each packet or prove which component produced every RTT sample. The tested HyStart also does not stop all startup loss: 200 drops remain.

All queued-visit counts satisfy `enqueued - dequeued = pending`, and samples equal dequeues. No `DropAfterDequeue` occurred; terminal pending counts are zero. Across all tagged flow-0 device visits, mean/max wait is 6.556362/114.632774 ms for near-on and 5.799456/114.632350 ms for near-off. A lower per-visit mean in the much lossier disabled flow is not proof of better queue behavior: the packet/visit population and congestion trajectory differ. Queue means include zero waits and are **not end-to-end delay or exact receiver buffer occupancy**. `queue_packets_at_flush` is measured at the explicit `flush_time_ns`, not at a fixed bin boundary. Device-queue drop counters being zero does not imply a lossless network; the TcDrop records above are separate.

### Forecast control and passive behavior check

The actual sending socket confirms CUBIC, HyStart enabled and `forecast_windows_ns=121600000000:121781136000`. The forecast control records **218 trace rows while the window is active**, including **108 eligible HyStart update samples**, but **zero `FORECAST_DEFER` events**. Its eventual exit is 0.496818080 s after the transition, outside the declared 0.181136-s horizon. The candidate was not retimed after observing this result, and no wider window was swept.

[`export.json`](assets/20261012-orbit-hystart/export.json) compares all **10 original v6 measurement CSVs** for near-on versus near-on-unobserved and for near-on versus near-forecast. Every file matches byte for byte. Wall-clock profiling and new observer files are excluded; raw hashes for every output remain preserved. The passive check spans the recorded source phases and therefore validates the combined inactive-policy/observer changes for this condition, not each possible hook independently. No independent-volume replay of the six cases was performed.

### Implementation version and scope

This tests the **supplied ns-3.48 HyStart implementation**, including its ACK-train detector and large clamped DELAY threshold. It is not an evaluation of HyStart++: [RFC 9406, Sections 4.1–4.3](https://www.rfc-editor.org/rfc/rfc9406.html#section-4.1) uses a delay detector and Conservative Slow Start to revisit a premature exit, with different delay constants. A defect in that modern algorithm is not established here.

The implemented opt-in variant changes only an ACK-train-only exit inside the declared oracle interval. A simultaneous DELAY decision and decisions outside the interval remain stock. The operator-oracle window comes from supplied routes/geometry; acquiring or transporting a forecast, clock error and unknown future queue delay are not modeled. No elevation/radio capacity model, path search, new constellation state, TCP kernel port, RACK implementation or competing-flow study was added.

## Exact artifacts and reproducibility

The first four cases use [`observed.patch`](../../code/orbit-hystart/observed.patch), SHA-256 `640660ca272feadb572ac84d3390dfcf88ec5e020b502c5bae3c51daa0058b8e`. The last two use [`ns3.patch`](../../code/orbit-hystart/ns3.patch), SHA-256 `2f6274c828a2d9a00e952092ba61ea834aed10de9e46748a837ab0a5595fdc7d`. Both include canonical v6 (`473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`) and apply as one combined patch to official ns-3 source HEAD `99bc6f733274475b7a6e804128651e17ee2a2536`. The initial pre-queue `passive.patch` was not used in a reported simulation.

[`README`](../../code/orbit-hystart/README.md) gives the exact two-phase reconstruction. Builds with `./ns3 build -j 1`, diff checks and reverse-apply checks passed. Each original raw manifest records actual commands/environment, launch commit and dirty flag, runner/patch/runtime binary-library hashes, configuration/schedule hashes, all 7 static and 4,000 dynamic input receipts, status, runtime and every raw output hash. Compact summaries preserve the manifest identity and input-map hashes. Source identities remain separate from later analysis helpers; the shared repository had ongoing uncommitted work, which is explicitly recorded rather than described as a clean launch commit.

The six simulation calls took **25.754 s of summed case wall time** (4.132–4.737 s each), excluding builds, intervals between calls, analysis and archiving. This is not one continuous workflow elapsed time. All six succeeded; no condition was timed out or left incomplete.

The verified local raw archive is `output/orbit-hystart-20261012.tar.gz`: **4,381,571 B compressed**, **32,884,348 B** across **139 regular members**, SHA-256 `752be45fb1ee1807cda5060a98bffa19769fdaf8312266a8ea7cf183d1f7c273`. [`raw-archive.json`](assets/20261012-orbit-hystart/raw-archive.json) records all member hashes and successful streamed verification of each member. It includes original manifests and traces, not the entire ns-3 tree/build or supplied state. Archive bytes and wall-clock timing are not expected to reproduce. The root's [shared publication inventory](20261012-parallel-candidates.md) records the prerelease asset URL and independently verified download/digest; this experiment record does not claim an upload by its author.

The candidate is **not selected for further improvement work in these conditions**: no harmful early exit was demonstrated, original HyStart helped, and the geometry-only horizon produced no action. Other workloads, settings, forecast horizons, implementations or paths remain untested.
