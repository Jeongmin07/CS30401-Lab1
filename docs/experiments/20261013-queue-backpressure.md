# Source FIFO/backpressure and CoDel controls

Status: all three declared Stage1 simulations completed and accounting checks passed. Neither queue candidate passed every prospective gate. These are environment/queue-management controls, not a new TCP algorithm.

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

Predeclare whole200, post `[75,75.5)` and focus `[74.5,77.5)` reports. The shared declaration also specified the first event `[25.7,28.2)`; that reporting window was added to this analyzer after the immutable batch, without changing the screening gates. A candidate aims for goodput at least0.995 of the matched control, at least50% lower post combined queue mean and served residence, at most5 unique all-layer tagged losses in focus, and no worse whole-run queue/wait/loss metrics. Always disclose exact deltas; these gates are screening criteria, not statistical significance or universal performance claims.

The new no-qdisc100 observer control must reproduce the completed selective+tail legacy CSV trajectory before interpretation. Runtime/source/input/output hashes and original launch/helper phases remain distinct. No new topology, geometric cap or routing intervention is included.

A narrow default-OFF helper may support a later, separately authorized physical-drop control: first source-observed original flow0 segment starting atseq1, drop exactly that tagged transmission at the receiver. Eligibility is sequence/transmission identity, not a fixed T26 timestamp across changed histories. It will not be enabled in these initial three conditions.

## Results

The final combined patch is `90f9114c9a31df219587aea1e9406dccaeb3c4891243699c5d825827369ac72f` (128,930 bytes). The successful final build took44.840930758 seconds, and all17 live binary/library hashes match [build-ready.json](../../code/queue-backpressure/build-ready.json). The [final build log](assets/20261013-queue-backpressure/final-build-log.txt) is preserved. Read-only source review cleared native queue accounting and actual root/qdisc loss coverage.

An initial development build was never simulated. Review then found that installing the qdisc after the legacy study observer would falsely label root absence and omit qdisc drops. The final source configures the discipline first and records IPv4-aware qdisc drop callbacks; no-qdisc legacy behavior remains unchanged. Initial source/build receipts are retained under `code/queue-backpressure/development-initial/` rather than presented as experimental attempts.

The actual three-case launch used shared source checkpoint `b6112ce8bd4e2be9c0508bb2cbded4aad1713dad`. Actual Git HEAD was that commit for control and `d5d6d2932a9b27b7dafe76072df9c96cf3c956e4` for FIFO/CoDel after unrelated repository work. Executed source/dependency/runtime hashes remained identical; a changed shared HEAD is not relabeled as the earlier commit. The runner command was:

```bash
python3 -B /work/code/queue-backpressure/run.py control100 fifo4-96 codel4-96 --root /tmp/queue-backpressure --timeout 600 --checkpoint b6112ce8bd4e2be9c0508bb2cbded4aad1713dad
```

These are original launch commands/paths; [fresh replay instructions](../../code/queue-backpressure/README.md) use new output paths and a fresh readiness receipt. Every case completed with exit0 and identical pre/post runtime and installed source. Wall times were39.944446177 seconds (control),41.047054936 (FIFO) and34.173414461 (CoDel). This track has three successful simulation attempts, no failed/timeout simulation, no Stage2 and no result-dependent tuning.

### Whole200 results

All means include actual queued state over the complete interval. Source residence is measured per successfully serializing packet, from TrafficControl ingress through all source queue stages.

| Condition | Ordered app bytes | Goodput Mbps | Combined source mean packets | Mean source residence ms | Unique data losses | RETX / recovery |
|---|---:|---:|---:|---:|---:|---:|
| Control100 | 238,662,720 | 9.5465088 | 36.098390140 | 41.724668257 | 486 | 507 / 40 |
| FIFO4+96 | 238,662,720 | 9.5465088 | 36.098390140 | 41.724668257 | 486 | 507 / 40 |
| CoDel4+96 | 223,508,940 | 8.9403576 | 2.795113506 | 3.432026149 | 171 | 174 / 46 |

FIFO reduced the source **device-only** mean from36.098390140 to3.953211445 packets, but32.145178695 packets waited in its qdisc. Combined source area, actual per-packet residence and network-plus-qdisc backlog are unchanged. The same486 data losses moved from no-root `TcDrop` to qdisc capacity rejection. This is queue relocation, not lower delay or fewer losses.

CoDel reduced the whole combined queue mean by92.257%, and served residence by91.775%, but whole goodput declined6.349454% (15,153,780 fewer ordered bytes). Its171 losses include54 overlimit drops and117 target-exceeded drops after qdisc dequeue; those117 are excluded from successful-service samples. Its serialization busy fraction was0.929351132 versus0.992441866 for control/FIFO. Those observations show a tradeoff; they do not isolate every cause of the throughput decrease. CoDel still reached a peak combined100 queued packets and a112.115947ms maximum served residence, so lower means do not mean all bursts disappeared.

### Declared event windows

| Window / condition | Goodput Mbps | Combined mean packets | Served residence mean ms | Unique data losses | RETX / recovery |
|---|---:|---:|---:|---:|---:|
| First25.7–28.2 / control | 9.622464 | 24.329360161 | 27.765263188 | 0 | 0 / 0 |
| First / FIFO | 9.622464 | 24.329360161 | 27.765263188 | 0 | 0 / 0 |
| First / CoDel | 9.481152 | 2.658714935 | 3.075923583 | 0 | 0 / 0 |
| Post75–75.5 / control | 9.62688 | 87.232380644 | 96.199543237 | 0 | 0 / 0 |
| Post / FIFO | 9.62688 | 87.232380644 | 96.199543237 | 0 | 0 / 0 |
| Post / CoDel | 9.56064 | 8.189702588 | 9.336581585 | 1 | 0 / 0 |
| Focus74.5–77.5 / control | 9.61952 | 48.717925536 | 56.736413246 | 11 | 12 / 2 |
| Focus / FIFO | 9.61952 | 48.717925536 | 56.736413246 | 11 | 12 / 2 |
| Focus / CoDel | 8.87616 | 2.639393320 | 3.282959831 | 1 | 1 / 1 |

Bounds are half-open. Application, loss and retransmission use their own event times; served residence uses serialization-start event time. A post-window drop can be retransmitted later, so counters in different rows are not interchangeable. Neither candidate passes all gates: FIFO misses the delay/queue halving and focus-loss gates; CoDel passes those but misses goodput retention (0.936505458 of control, below0.995). Neither is selected for a later safety experiment in this track.

### Validation and preservation

The no-qdisc control reproduced all12 previous selective+tail measurement CSVs exactly by size/SHA, with identical configuration, schedule and supplied static/dynamic state. Across all three cases the actual source/dependency hashes, runtime17 hashes, patch, readiness, inputs and policy parameters match; only the declared queue mode/maxima and output locators differ in the executed configuration. [Compact case manifests](assets/20261013-queue-backpressure/cases/control100.json), [matched comparison](assets/20261013-queue-backpressure/analysis.json) and [12-row results table](assets/20261013-queue-backpressure/results.csv) retain the exact values, all four windows, percentiles and native counters.

Source ingress conservation was173,534 =173,022 served +486 discarded +26 pending for control/FIFO, and162,197 =162,023 +171 +3 for CoDel. FIFO's pending26 comprised22 qdisc +4 device packets; CoDel's pending3 were device packets. Every case separately had one serializing packet at cutoff, outside queued/pending counters. Ordinary requeues were observed as0, rather than assumed absent. Device/qdisc conservation, independently measured device/source packet area, serialization busy time and complete loss identity joins all passed.

Loss counts are **tagged payload-bearing transmitted data**, deduplicated across layers by full flow/tx_id/TX-time/sequence/payload identity and joined to sender TX. ACK/control or untagged drop notifications were separately counted as0 in these cases. Root presence and qdisc drop hooks are explicitly checked; the legacy generic root-absence convention must not be applied to candidates. Source waiting is complete across qdisc/device/requeue, and all visited downstream native queues are also integrated. This prevents interpreting moved backlog as a gain. Dropped residence and censored pending ages remain separate from served samples.

Original launch analyzer SHA was `52763aabc17748db1528360819bd8241611a9ebc3757fc7aba87e9f50bb95b29`. After all runs, reporting-only additions supplied the missing first window and explicit matched-input/runtime receipts; actual analysis helper SHA is `1b04dcf7bd2ca3439caebdfcecf28fb1c377a0eea15dcdee5767786c3c5901b5`. No simulator, runtime, original manifest or raw log changed. Analysis JSON SHA is `63597aa8b5e175abaf7ff0826358b99df2eff282d3a53fa5fa9325f164869c48`; [export receipt](assets/20261013-queue-backpressure/export.json) records the separate export helper phase.

All114 raw regular-file members are preserved in `output/queue-mitigation-raw/queue-backpressure-20261013-raw.tar.gz` (53,744,979 bytes), SHA `7b844773692b7aaaeb70522d036a49e6036d901e7578c7a6e7c3788c82a34533`. [The inventory](assets/20261013-queue-backpressure/raw-inventory.json) stream-verifies every archived byte/hash. The [common publication record](20261013-queue-mitigation.md) maps release assets and independent publication verification. This deterministic natural trace is an engineering screen, not statistical significance or proof of general CoDel/TCP/LEO behavior.
