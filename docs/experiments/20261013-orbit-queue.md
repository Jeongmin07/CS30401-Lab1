# Paired device-queue audit around the 75-second route transition

Status: natural pair completed and verified; conditional routing input prepared for independent review, 13 October 2026. This is an independent diagnostic; it does not select the team's final topic. Existing study directories, source volumes and policies remain frozen.

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

The posthoc analyzer initially used the new observer's `node_id/packet_uid` names for the unchanged legacy `study_drops.csv`, whose fields are `node/uid`. Only this analysis alias was corrected after both simulations; no source/runtime or simulation was rerun. The evidence preserves the launch analyzer hash separately from the final helper hash.

The paired result warrants the single predeclared routing counterfactual. `delay_route.py` copied the supplied state and changed exactly two files: empty the original T75 delta and place its unchanged 30 rows at T78. Construction/validation took 13.103793 seconds. The [actual replacement files](assets/20261013-orbit-queue/routing-replacements.json) total 514 bytes. All 75.1–78.0 frames are empty in the original input, all earlier/static/capacity/other dynamic bytes are unchanged, and original future overrides remain intact. [Construction receipt](assets/20261013-orbit-queue/route-delay-input.json) validates the accumulated state, actual interface types and ISL counterpart identities, and all source-to-endpoint routes in both states at each of 32 affected frames. Both forward and reverse routes/link choices remain old until T78. The original T75 forecast/policy schedule stays unchanged; this is a fixed-policy routing intervention, not a deployed controller reforecast for T78. Native ideal shared-channel GSL validity does not prove physical visibility. Independent review and the parent chat's checkpoint are required before this third simulation; its execution is still pending.

Raw inventories, final conditional results and publication links will be added after execution. Publication and common PR/Release records belong to the parent chat.
