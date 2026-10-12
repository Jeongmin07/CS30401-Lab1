# Source FIFO/backpressure and CoDel controls

Status: implementation/predeclaration, simulations 0. These are environment/queue-management controls, not a new TCP algorithm.

Use the pinned official image, a separate `lab1-queue-backpressure-20261013` container and `cs30401-queue-backpressure-ns3-20261013` volume, two CPUs, 4 GiB, one build job and 600-second cap per simulation. Preserve exact tail policy base `5b847bbafe8d950072b5bc34e0420da8f7f1c860bc7fcc94c3c3ab8b37bb4d29`, selective forecast/schedule, tail-enabled bulk semantics, unchanged supplied forwarding/capacity inputs and all other queues. Wait for source review and the parent chat's shared checkpoint before any simulation.

## Fixed initial matrix

All three conditions are one Seoul1584→London1585 100GB flow starting at0, CUBIC, no pacing, natural supplied routing, 10Mbps, 200 seconds. Change source node1584/device1 only.

| Condition | Source device queue | Root queue discipline |
|---|---:|---|
| Existing control | 100 packets | none |
| FIFO/backpressure | 4 packets | FifoQueueDisc, 96 packets |
| CoDel/backpressure | 4 packets | CoDelQueueDisc, 96 packets |

4+96 matches the nominal queued-packet capacity. A qdisc requeued item and the device's in-service packet lie outside those counters and must be measured separately; this is not a claim of a strict100-resident-packet limit. CoDel uses native Target5ms, Interval100ms, MinBytes1500, UseEcn=false and UseL4s=false. Only its capacity is bounded to96 packets; no result-dependent parameter change or T75 tuning is planned.

The course GSLHelper already creates NetDeviceQueueInterface and connects queue traces. Native TrafficControl initialization binds QueueDisc::Run to Wake; the qdisc waits while the device queue is stopped. The course removes root disciplines after IP assignment, explaining the earlier direct stopped-device discard. Attaching a standard root discipline before simulation initialization is supported. CoDel above an unchanged100-packet device queue would miss much of the waiting below it, so the matched FIFO4+96 control is necessary. CoDel's delay control and standard parameters are described in [RFC8289](https://www.rfc-editor.org/rfc/rfc8289.html), especially sections3.1 and4.2–4.5; native queue-discipline integration is described in the [ns-3 model documentation](https://www.nsnam.org/docs/models/html/queue-discs.html).

## Measurements and prospective gates

Measure ordered app goodput and exact tagged transmission losses at **all layers**, including deliberate CoDel drops. A reduction in device/TcDrop alone does not count as a benefit. Deduplicate loss notifications by full flow/tx_id/tx_time/sequence/payload identity and preserve original reasons/locations. Report untagged/unmapped drops separately.

Integrate exact packet/byte state changes into sparse100ms time-area bins for every visited native device queue, the source qdisc and combined queued/requeued state over the complete200 seconds. Do not substitute queue-at-flush snapshots. Report the serializing packet separately. Measure actual source residence from TrafficControl ingress to PhyTxBegin per packet, including qdisc/device/requeue waiting; do not add averages from different visits. Dropped and pending items have separate observed/censored residence. Reconcile ingress/served/drop/pending and each layer's native counters. CoDel dequeue/drop-after-dequeue is not successful service.

Predeclare whole200, post `[75,75.5)` and focus `[74.5,77.5)` reports. A candidate aims for goodput at least0.995 of the matched control, at least50% lower post combined queue mean and served residence, at most5 unique all-layer tagged losses in focus, and no worse whole-run queue/wait/loss metrics. Always disclose exact deltas; these gates are screening criteria, not statistical significance or universal performance claims.

The new no-qdisc100 observer control must reproduce the completed selective+tail legacy CSV trajectory before interpretation. Runtime/source/input/output hashes and original launch/helper phases remain distinct. No new topology, geometric cap or routing intervention is included.

A narrow default-OFF helper may support a later, separately authorized physical-drop control: first source-observed original flow0 segment starting atseq1, drop exactly that tagged transmission at the receiver. Eligibility is sequence/transmission identity, not a fixed T26 timestamp across changed histories. It will not be enabled in these initial three conditions.

## Results

Pending source integration, build, review and shared checkpoint. No simulation has been launched.
