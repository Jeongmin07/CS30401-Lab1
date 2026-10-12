# Fixed native CUBIC pacing controls for device-queue overflow

Status: pre-simulation declaration, 13 October 2026. Existing study directories and volumes stay frozen. This track owns `code/queue-pacing` and these new assets; the parent chat owns commits and publication.

## Question and evidence

The [T75 queue audit](20261013-orbit-queue.md) identifies literal fullness of the source GSL device queue and attributable TrafficControl rejections. Delaying the route transition to T78 still produced11 rejections before the transition, so the route switch is not necessary for that overflow. The larger selective queue also precedes T75. The question here is whether native pacing, with or without operator-known capacity information, reduces the sender's congestion/burst cost while retaining ordered receiver throughput. It is not an orbital-cause or new congestion-control-algorithm claim.

All initial conditions retain the complete200s history, physical10Mbps links, q100 packets, Seoul1584→London1585,100GB flow0 starting at0, original routing/state and current selective+tail policy. Tail is inert for this unfinished bulk. No topology, outage, random wireless loss, selected-start-at75 or rate sweep is introduced.

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
