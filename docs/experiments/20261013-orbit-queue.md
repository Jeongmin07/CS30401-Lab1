# Paired device-queue audit around the 75-second route transition

Status: all three declared conditions completed, raw/evidence verification passed, 13 October 2026. This is an independent diagnostic; it does not select the team's final topic. Existing study directories, source volumes and policies remain frozen.

## Question and fixed scope

Does avoiding the 26.2-second presumed-loss recovery leave a different CUBIC/congestion phase that reaches a full source-device queue around 75 seconds? The prior final V2 raw traces show 190,440 versus 240,120 bytes of cwnd at T75, and selective source-node TcDrop events at 75.591584423–75.821089639 seconds. They do not directly measure selective queue occupancy or isolate propagation shortening from an ordinary CUBIC congestion cycle. SRTT is not queue sojourn, and the TcDrop device sentinel is not a measured device identity.

Run exactly two pure-observer natural conditions initially: final V2 baseline K3 and selective K3, each 10 Mbit/s, q100 packets, Seoul1584→London1585, one 100GB flow starting at zero, simulation end 200 seconds. Preserve the full start-to-75 history, both original directional routes, and final V2 geometry/wait/budget inputs. Do not introduce a cwnd cap, pacing, new topology, outage, or parameter sweep. The source base is the complete `code/orbit-loss/ns3.patch`, SHA256 `531bf802984af821afd928fb3932912aca383fcdec5771f30f78d75a806d5591`.

Use a separate pinned official container `lab1-orbit-queue-20261013`, volume `cs30401-orbit-queue-ns3-20261013`, two CPUs, 4 GiB and one build job. Preserve build/source/runtime receipts and wait for the parent chat's shared source/declaration checkpoint before the first simulation. Each run has a 600-second wall cap; failed/timeout attempts are preserved and excluded from completed comparisons. Never rebuild or mutate runtime during a simulation.

## Passive source hooks

Read the actual official source before adding observers. Device queue enqueue/dequeue, occupancy, served sojourn and serialization busy use packet-object identity internally, because fragments can share UID. Track the complete run with compact bins and record exact queue/occupancy/served events in `[74.5,77.5)`. Device/flow identities, pending packets and queue-conservation checks are preserved.

Add observation-only hooks after NetDeviceQueue changes its device-stop or BQL-stop flags. Record reason, both flags before/after, combined IsStopped and whether a wake callback would run. A wake of one flag need not make the queue runnable. Read flags without invoking a new state-changing calculation. In TrafficControlLayer::Send, record the actual node/device/txq and both stopped flags immediately before the existing no-root-qdisc drop callback; preserve the original drop and send behavior. Join those records to exact queue depth/max size and original flow/tx tag. Record queue-limit presence/type rather than assuming that every stopped queue is full.

Observations are opt-in and default off. No TCP threshold, loss marking, SACK/PRR, ACK, cwnd, routing or timer decision is changed. Compare original V2 measurement CSV bytes/hashes separately for each natural condition; timing profiling and new observer files are excluded, while source/runtime identities remain separate. A mismatch stops causal interpretation until explained.

## Measurements and inference boundary

Use fixed pre `[74.5,75)`, post `[75,75.5)`, legacy `[74.5,77)` and focus `[74.5,77.5)` windows, plus complete 200-second app delivery/goodput and the earlier 26.2-second policy events. Keep every queue's identity and direction. Compare occupancy over time, packet-weighted served wait, pending ages, queue-full/stop intervals, serialization busy, exact actual-drop identity/time, cwnd/pipe and policy action counts. Flush occupancy is not automatically a bin-boundary snapshot; wire arrival is not ordered app delivery.

A source drop at a stopped device can establish the local discard mechanism when its actual flags and queue state are joined. It does not alone show that the 75-second route change, rather than the pre-existing congestion phase, caused it. More/larger flight can support that hypothesis but is not itself per-device queue occupancy.

## Conditional counterfactual, at most one additional run

Only if the paired observation warrants the route-cause question, consider one selective condition that delays the 75.0-second supplied routing transition until **78.0 seconds**, beyond the focus window. Preserve earlier policy/history and all other run inputs. This is a routing counterfactual, not a deployed control or a pure-geometric latency experiment.

Do not merely remove an empty or nonempty 75.0 file. Accumulate all supplied sparse forwarding deltas, identify the changed keys, inspect subsequent overrides at every 100-ms frame, and construct a delayed transition with explicit semantics. Validate forward and reverse endpoint paths for every affected frame: no loop, missing next hop, invalid neighbor/interface or accidental override. Record original/modified file hashes and complete state receipt. If old choices cannot safely be retained or unrelated routing changes cannot be preserved, stop before running this condition and report the narrower device-level inference. If both directions and link choices change, disclose them explicitly. The parent chat reviews this construction before its run.

The initial maximum is three successful simulations: the two natural observers plus this one conditional counterfactual. No cap/pacing policy or further sweep is authorized here.

## Results and preservation

The initial pair ran from shared checkpoint `66b2409f722bc68e3a4973254ceb599c3d6b5892`, using the same immutable combined patch `f0e85cab5a351e67d95a80d098cf65cf509300f73077e27b2d35dd6cbaf3e301` and executable `647a0359399d97cec58447afab03ca11b50290904275723fe323520c59b026ba`. The single-job build took 438.974510 seconds. Both simulations completed with exit 0: baseline 64.071784 seconds, selective 69.966455 seconds. The baseline's 10 and selective's 11 original measurement CSVs match the final V2 originals byte for byte; timing and newly added observer CSVs are excluded. Config, schedule and accumulated input-state identities also match. Every observed per-device/per-flow enqueue/dequeue/pending conservation check passed, and exact stopped-device drop records match the original TcDrop multiset.

[Natural-pair evidence](assets/20261013-orbit-queue/natural-pair.json) identifies the source queue as node 1584, device/interface 1, transmit queue 0, `GSLNetDevice`, `DropTailQueue<Packet>`, maximum `100p`, no root queue discipline and no QueueLimits/BQL object. Both source serializations remain 100% busy in all declared focus subwindows.

| Source-device measure | Baseline | Selective |
|---|---:|---:|
| Mean queued packets, `[74.5,75)` | 43.350086 | 71.178560 |
| Peak queued packets, `[74.5,75)` | 48 | 79 |
| Mean queued packets, `[75,75.5)` | 53.270929 | 87.232381 |
| Peak queued packets, `[75,75.5)` | 59 | 97 |
| Mean served visit wait, `[75,75.5)` | 59.623105 ms | 96.199543 ms |
| First literal-full/DEVICE_STOP in focus | 77.040772827 s | 75.564051455 s |
| First exact source-device TcDrop in focus | 77.066011375 s | 75.591584423 s |
| TcDrop, `[74.5,77)` | 0 | 11 |
| TcDrop, `[74.5,77.5)` | 12 | 11 |
| Literal-full time, `[74.5,77.5)` | 55.590982 ms | 22.661582 ms |

There are no literal-full intervals or drops before T75 in the prewindow. Every focus rejection is attributable to the same source-device queue, with exactly 100 queued packets/143,400 bytes, device-stop true, BQL-stop false and the one-MTU overflow test true. These are TrafficControl rejections before device enqueue; zero Queue::DropBeforeEnqueue callbacks do not imply no network loss.

The larger selective queue is already present before the route switch. After selective recovery, the complete `[74.5,77.5)` mean occupancy is **lower** (48.717926 versus 67.179912 packets). This establishes a different congestion phase and a local full-device-stop discard mechanism; it does not establish a continuously higher queue or route shortening as the sole cause. Whole-run app goodput remains 9.544356 versus 9.5465088 Mbit/s.

The posthoc analyzer initially used the new observer's `node_id/packet_uid` names for the unchanged legacy `study_drops.csv`, whose fields are `node/uid`. This analysis alias was corrected after both simulations. Independent review then strengthened dropped-transmission identity to time/node/UID/flow/tx_id/tx_time/sequence/payload, because UID can repeat in simultaneous bursts; every tagged data drop also matches a sender TX row. The finalized exports were regenerated without rerunning or modifying any simulation, original manifest or runtime. Earlier intermediate exports remain outside Git in `/tmp/orbit-queue-prior-analysis`. [Phase receipt](assets/20261013-orbit-queue/phases.json) separates launch helpers from final posthoc helpers.

The paired result warranted the single predeclared routing counterfactual. `delay_route.py` copied the supplied state and changed exactly two files: empty the original T75 delta and place its unchanged 30 rows at T78. Construction/validation took 13.103793 seconds. The [actual replacement files](assets/20261013-orbit-queue/routing-replacements.json) total 514 bytes. All 75.1–78.0 frames are empty in the original input, all earlier/static/capacity/other dynamic bytes are unchanged, and original future overrides remain intact. [Construction receipt](assets/20261013-orbit-queue/route-delay-input.json) validates the accumulated state, actual interface types and ISL counterpart identities, and all source-to-endpoint routes in both states at each of 32 affected frames. Both forward and reverse routes/link choices remain old until T78. The original T75 forecast/policy schedule stays unchanged; this is a fixed-policy routing intervention, not a deployed controller reforecast for T78. Native ideal shared-channel GSL validity does not prove physical visibility.

Independent input/runner review cleared before the third run. Shared checkpoint `3767411cb0f154e7b40b7c098f9516f1c47fbc73` launched it with the same patch and 17 runtime hashes; it completed exit 0 in 29.789788 seconds. The [counterfactual evidence](assets/20261013-orbit-queue/counterfactual.json) verifies 16 temporal/projected pre-T75 comparisons and four full static files, preserving original app/packet/cwnd/RTT/drop/policy and observer histories. Bin flush/final-cutoff fields are excluded from temporal prefix comparisons because they may observe a later time. This is not a claim that 20 entire output files are identical. Counterfactual input/config differences are exactly the declared two routing files and the two directory locator properties; schedule bytes remain identical.

| Source-device focus measure | Selective natural T75 switch | Selective switch delayed to T78 |
|---|---:|---:|
| Post `[75,75.5)` mean queued packets | 87.232381 | 85.875350 |
| First literal-full/DEVICE_STOP | 75.564051455 s | 75.617356228 s |
| First TcDrop | 75.591584423 s | 75.644889535 s |
| Focus TcDrop / retransmissions / recovery entries | 11 / 12 / 2 | 11 / 12 / 2 |
| Focus literal-full time | 22.661582 ms | 95.664354 ms |
| Focus mean queued packets | 48.717926 | 50.089641 |
| Whole app goodput | 9.5465088 Mbit/s | 9.5465088 Mbit/s |

The route delay shifts the first rejection by 53.305112 ms, yet the same local queue still reaches 100 packets and rejects 11 transmissions **before the delayed switch occurs**. Thus the T75 route switch is not necessary for this overflow in the tested fixed-policy state. Routing affects the measured timing and queue evolution, so this is not evidence that routing has no influence. Packet identities/trajectories differ after T75 even though the listed whole-run app/retx/recovery/drop totals agree.

Both conditions have zero selective wait actions in the focus and delayed-transition windows; the original 26-second episode remains unchanged. The descriptive `[77.5,80.5)` window has zero TcDrop/retransmissions/recoveries in both conditions, with equal app goodput 9.6232 Mbit/s. Exact occupancy logging ends at 77.5; later aligned queue bins report served-visit wait only, not direct time-weighted occupancy. This diagnostic does not test or establish the effectiveness of a geometry-only cwnd cap.

## Reproduction and raw preservation

Exactly three simulations were launched and completed; none failed or timed out, and no further condition was added. Wall runtimes reflect concurrent local load and are not network-performance comparisons. This track verifies added-observer equivalence to completed final V2 runs and the conditional input prefix; it does not claim a separate clean-volume replay or final assignment ZIP validation.

Original launch commands (historical paths/receipts; use new outputs for reconstruction):

```text
python3 -B /work/code/orbit-queue/run.py base-natural selective-natural --root /tmp/orbit-queue --timeout 600 --checkpoint 66b2409
python3 -B /work/code/orbit-queue/delay_route.py --receipt /work/docs/experiments/assets/20261013-orbit-queue/route-delay-input.json
python3 -B /work/code/orbit-queue/run_cf.py --receipt /work/docs/experiments/assets/20261013-orbit-queue/route-delay-input.json --checkpoint 3767411 --root /tmp/orbit-queue-cf --timeout 600
```

The original launch versions remain in those checkpoints. The final CF wrapper adds `--ready` after launch as a CLI-only portability change, allowing a fresh build receipt and its matching fresh natural pair without overwriting the original readiness. See the [runner README](../../code/orbit-queue/README.md). Final analysis tools are posthoc, with separate hashes and no new TCP/runtime behavior.

| Verified raw archive | Bytes | Members | SHA256 |
|---|---:|---:|---|
| `orbit-queue-natural-20261013.tar.gz` | 24,629,094 | 59 | `cfafbeae5f4761f53d0e823da84ee3388ff28b6817e67c05e8e2285c5310e064` |
| `orbit-queue-route-delay-20261013.tar.gz` | 12,306,772 | 30 | `f852d8bbe44e6b5be4da7b6487172f5e0b29df5f0755f829162754dde8fc6157` |

Every member was rehashed against the unchanged run files: [natural inventory](assets/20261013-orbit-queue/natural-raw-inventory.json), [conditional inventory](assets/20261013-orbit-queue/counterfactual-raw-inventory.json). Archives reside in ignored `output/tail-queue-raw`; the two tiny routing replacements and construction recipe reconstruct the conditional input from the pinned supplied state, without archiving a new topology. Image/resource identity is in [environment.json](assets/20261013-orbit-queue/environment.json), and the single-job build output is [final-build-log.txt](assets/20261013-orbit-queue/final-build-log.txt).

Publication and shared Release verification are tracked in the [common follow-up record](20261013-tail-and-queue.md), maintained by the parent chat.
