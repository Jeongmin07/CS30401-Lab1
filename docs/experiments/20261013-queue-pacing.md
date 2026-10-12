# Fixed native CUBIC pacing controls for device-queue overflow

Status: completed, 13 October 2026. All eight predeclared conditions succeeded on one immutable runtime. There were no failed or excluded simulation attempts. The declaration below preceded the runs; the [final comparison](assets/20261013-queue-pacing/final/comparison.json) preserves its gates. Existing study directories and volumes stayed frozen. The parent chat owns commits and publication.

## Outcome and scope

The operator-capacity ceiling passes the fixed **long, single-flow bulk** gates. Native pacing alone fails throughput preservation. The selected setting is an opt-in result for this known fixed-capacity model; it is not a safe global default for all transfers. Its finite genuine-loss control takes **0.471434773 s instead of 0.257223678 s**, an **83.28% regression** against current selective+tail.

| Natural 200 s case | Ordered goodput (Mbps) | Distinct dropped transmissions | RETX / recovery / CA_LOSS | All-device queue packet-seconds |
|---|---:|---:|---:|---:|
| `off` | 9.5465088 | 486 | 507 / 40 / 1 | 7858.720495 |
| `native` | 9.0571056 | 460 | 471 / 29 / 10 | 6736.523791 |
| `capacity` | 9.5662704 | 0 | 2 / 1 / 0 | 632.853245 |

Capacity goodput increases 0.2070%, while whole all-device queue packet-time falls 91.947%. Native-only goodput falls 5.1276% and misses the predetermined 9.498776256 Mbps floor. CA_LOSS is the actual congestion-state count; these rows do not independently prove how many RTOs occurred.

| Source GSL queue, fixed post `[75,75.5)` | Mean queued packets | Mean served wait (ms) | Actual served visits | Focus `[74.5,77.5)` distinct drops |
|---|---:|---:|---:|---:|
| `off` | 87.232381 | 96.199543 | 435 | 11 |
| `native` | 26.501644 | 30.101378 | 436 | 0 |
| `capacity` | 0 | 0 | 436 | 0 |

The zero post source wait has 436 actual served visits; it is not a no-traffic window. Over the whole run, source mean served wait is 41.724668 ms OFF versus 0.000456345 ms with the ceiling. Those means divide total source sojourn by total served visits. **Other device queues still contribute 632.774133 packet-seconds** in the capacity case. Zero source post wait therefore does not mean zero network queueing or zero end-to-end delay. [Exact whole sums and visit denominators](assets/20261013-queue-pacing/final/posthoc.json) are retained separately.

The capacity bundle still uses selective waiting: its 26.2 s epoch actually defers three eligible sequences from 26.308522212 to 26.314194176 s, lasting 5.671964 ms. The 75 s epoch registers but starts no wait; natural tail admissions are zero. Compatibility metrics such as `guard_starts=0` describe old threshold setters, **not absence of selective K3 waiting**. No capacity-only/stock-TCP ablation was run, so this comparison identifies the native pacing setting's effect while keeping the existing selective+tail bundle.

Two retransmissions remain around 121.6 s. Exact original TX tags match receiver RX, expected sequence and same-time ordered APP frontiers **before** the later RETX, with triggering RX_ACK/SACK and recovery rows retained in the [posthoc witness](assets/20261013-queue-pacing/final/posthoc.json). This directly establishes unnecessary retransmission, beyond merely observing zero drops. Geometric shortening is not established for that episode; this bundle does not solve every reordering event.

## Safety controls and their cost

| Stable 4 s, 20 MSS transfer, true first loss | Receiver FCT (s) | Extra tail admissions | RETX / recovery / distinct drops |
|---|---:|---:|---:|
| `micro-original`: original TCP, pacing OFF, tail OFF | 0.251509920 | 0 | 1 / 1 / 1 |
| `micro-current`: selective+tail, pacing OFF | 0.257223678 | 1 | 1 / 1 / 1 |
| `micro-selected`: selected native paced bundle | 0.471434773 | 0 | 1 / 1 / 1 |

The selected micro's actual initial native rate is 2.208 Mbps, far below its scaled 96.234309 Mbps ceiling, and spaces payload packets by 5 ms. Before recovery it sends new sequences 13801 and 15181 at 200.248 and 205.248 ms: the first is just before the actual selective wait starts at 200.477440 ms, and the second is inside it. At every SACK-triggered tail check, 12420 bytes remain unsent, exceeding the one-MSS precondition; the trace records `MORE_THAN_ONE_MSS`, not `PACING_TIMER`. The same deadline/head RETX remains 207.108958 ms, but the last original sequence 26221 is sent only at 421.320053 ms. This is a changed native sender-rate and recovery trajectory, not proof that a tiny tail-timer integration fix would remove the cost. No repair or further rate was tested.

| Bulk first-sequence-loss stress | Goodput (Mbps) | Distinct drops | RETX / recovery | Physical drop→first RETX (ms) |
|---|---:|---:|---:|---:|
| `loss-current` | 9.3421584 | 192 | 215 / 37 | 53.228969 |
| `loss-selected` | 9.3326640 | 1 | 3 / 2 | 53.228969 |

Selected stress goodput decreases 0.1016%. Each selected original flow0 sequence1/1380B transmission has an exact sender identity, physical destination GSL drop and receiver-time join; both observed selections happen to be identical. Shared rules would not guarantee that equality under other pacing conditions. This is a **startup true-loss** control before the active forecast epochs, not proof of loss detection during an active guard, finite-flow safety, or all RTO/ECN/receiver-window boundaries. [Paired identities and actual loss timing](assets/20261013-queue-pacing/final/posthoc.json) are explicit.

## Question and evidence

The [T75 queue audit](20261013-orbit-queue.md) identifies literal fullness of the source GSL device queue and attributable TrafficControl rejections. Delaying the route transition to T78 still produced 11 rejections before the transition, so the route switch is not necessary for that overflow. The larger selective queue also precedes T75. The question here is whether native pacing, with or without operator-known capacity information, reduces the sender's congestion/burst cost while retaining ordered receiver throughput. It is not an orbital-cause or new congestion-control-algorithm claim.

All initial conditions retain the complete 200 s history, physical 10 Mbps links, q100 packets, Seoul1584→London1585, 100 GB flow0 starting at0, original routing/state and current selective+tail policy. Tail is inert for this unfinished bulk. No topology, outage, random wireless loss, selected-start-at75 or rate sweep is introduced.

## Fixed initial3 conditions

| Case | Native pacing | MaxPacingRate | Other native settings |
|---|---|---|---|
| `off` | false | 4Gbps default | SsRatio200, CaRatio120, PaceInitialWindow=false |
| `native` | true | 4Gbps default | same defaults |
| `capacity` | true | 9623430bps | same defaults |

`tcp_enable_pacing=true` enables the original main driver. Native `UpdatePacingRate` uses `max(cwnd,pipe)*8/SRTT` times2 in early slow start or1.2 later, clipped by MaxPacingRate. This is measured SRTT and cwnd, not geometric propagation RTT. The native initial window remains unpaced. Direct retransmission paths can send while the pacing timer is running, so this is not a strict aggregate wire shaper.

`SendDataPacket` schedules native pacing using payload size. Full data payload is1380B while the observed serialized packet is1434B. The capacity setting is the predetermined operator ceiling `floor(10000000*1380/1434)=9623430bps`. A payload ceiling of10Mbps would exceed the10Mbps serialized link. The54B overhead assumption is disclosed and checked against actual packets; ACK/control traffic, variable packet sizes and retransmissions remain measured costs. No rate is chosen after seeing results.

## Prospective success and measurements

The reference whole goodput is9.5465088Mbps; preservation requires at least99.5%, **9.498776256Mbps**. The aim is no decrease, at least50% reduction in source post `[75,75.5)` time-weighted queued packets and packet-visit-weighted served wait, focus `[74.5,77.5)` attributable drops≤5, and no increase in whole-run all-device queue packet-time or distinct tagged drops. These gates are fixed before execution. If both paced controls pass, choose the one with fewer whole distinct drops, then lower whole queue packet-time, then higher whole goodput; a complete tie prefers native defaults. No later rate tuning follows a failure.

Keep fixed pre `[74.5,75)`, post `[75,75.5)`, legacy `[74.5,77)` and focus `[74.5,77.5)` windows, plus whole `[0,200)` and earlier26.2s evidence. Track ordered app bytes, actual RETX/recovery/CA_LOSS, all-device/drop-layer identities, source serialization utilization, device-stop/full intervals, pending ages and served visit waits. SRTT is reported separately from queue sojourn. CA_LOSS is not relabeled RTO without timer evidence.

New passive state integration records exact per-device100ms-bin `q_packet_ns`, `q_byte_ns`, maximum state and `full_ns` over0..200. Separate packet-count and byte-count callbacks integrate the previously held state before updating it; equal-time callbacks accrue zero elapsed area. Sparse zero bins are omitted and mean occupancy denominators include the complete declared time. Final held state is closed at200s. Late-flush queue snapshots are not used as time-weighted occupancy. All enqueue/dequeue/pending conservation and exact sender-TX/drop identities are checked. Baseline legacy measurements must match completed current-tail controls before causal interpretation.

## Conditional safety stage: at most5 additional conditions

Only after an initial paced winner meets the fixed gates, run5 safety controls on the same built runtime:

1. Stable50→50ms,100Mbps/q2000,4s,20MSS actual first loss: original TCP/pacingOFF/tailOFF; current selective+tail/pacingOFF with its existing false hint; selected native-paced selective+tail with the same hint. The native micro driver exposes an explicit enable-pacing flag because its current CUBIC setup otherwise overrides the global attribute. If the capacity setting wins, the same formula scales to `floor(100000000*1380/1434)=96234309bps` at physical100Mbps. Pacing may prevent the existing extra-tail hook from acting; actual admission/FCT and downstream recovery must be reported rather than assumed.
2. Full200s bulk with a single directed evaluation loss: current selective+tail/pacingOFF versus the selected setting. Drop the first original flow0 seq1/1380B transmission at the destination receiver, exactly once. Verify each run's own actual TX and physical drop identity/time. Pacing can change transmit timing, so shared rules do not imply the same transmission instance. This is a genuine-loss stress control, not a claimed T26 matched packet.

Finite completion or actual-loss regression remains an explicit application limit even if bulk queue gates pass. No parameter repair or expanded matrix is selected for a good result. This track has at most8 simulations (initial3+conditional5); the parent's parallel track has its own3 initial conditions, giving common maximum11 if this safety stage is used.

## Source and execution plan

Use a new pinned official container/volume, CPU2,4GiB, build-j1,600s wall cap per simulation. Base is the exact standalone current tail patch SHA256 `5b847bbafe8d950072b5bc34e0420da8f7f1c860bc7fcc94c3c3ab8b37bb4d29`. Compose copied passive queue/service/flow observers from the prior audit and the new exact integral logger; no native TCP pacing/recovery/loss decision is changed. Add the tiny micro CLI exposure and default-OFF evaluation loss support before the build. Export one combined patch, runtime/source/build/input/output receipts and preserved build log. Wait for the parent's final shared source checkpoint before any simulation.

No statistical repetition, capacity sweep, traffic competition, prediction-error study, wireless outages, Linux RACK/TLP or operational deployment claim is part of these controls. Added-observer source equivalence, native behavior, observed limits and actual costs remain separately identified.

## Execution and preservation

Dedicated container `lab1-queue-pacing-20261013`, volume `cs30401-queue-pacing-ns3-20261013`, official image digest `3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`, CPU2/4GiB/build-j1 were used. All eight runs retain combined patch SHA256 `ace08b170b04774c2eac849c1875e647a97e786611616cbb32867496cb2cb808` and all 17 runtime hashes. Initial source checkpoint was `3e456b706cfa779654e0f3ec15a132fa6415c7d6`; the prospectively selected five-case safety stage used checkpoint `a3cb6c575988fd895388ce17764e32bb7f95bffe`. Actual launch commits and dirty flags remain in each manifest.

The OFF control's 12 legacy measurement CSVs match the frozen current-tail run byte-for-byte, including actual selective/tail traces. Micro original/current controls also match their prior measurements; wall profiling is excluded. [Final matched comparison](assets/20261013-queue-pacing/final/comparison.json), [build/dependency receipt](assets/20261013-queue-pacing/source-build-receipt.json), [final readiness](assets/20261013-queue-pacing/build-ready.json), and preserved development/final build logs distinguish simulator provenance from postprocessing. The initial simulation-free build was followed by a fail-closed optional error-model overwrite guard and rebuild; it was not another simulation or performance-tuning attempt. `posthoc.py` was added only after all eight runs for explanatory witnesses and whole served sums.

Raw archive `queue-pacing-20261013.tar.gz`: **65,905,317 bytes**, SHA256 `db3eb38196ac4a61e76051b31a0c6cca86e11e1c680f032e7b0266014d9391be`, 220 byte-verified members. [Inventory](assets/20261013-queue-pacing/archive-inventory.json) distinguishes launch outputs from derived `analysis.json`, without changing original success manifests. The parent chat publishes and verifies the new [queue-mitigation release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/queue-mitigation-20261013); this track does not claim an independent upload. The [common selection and synthesis](20261013-queue-mitigation.md) includes the separate backpressure controls.

The fixed operator ceiling assumes the configured physical capacity and observed data-packet overhead. Uncertain available bandwidth, additional traffic, multiple TCP flows, smaller payloads, other headers and prediction error remain untested. This evidence supports a bounded known-capacity bulk setting with explicit finite-transfer costs, not a new algorithm, universal improvement or deployment recommendation.
