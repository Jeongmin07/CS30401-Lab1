# Paired device-queue audit around the 75-second route transition

Status: declared before simulation, 13 October 2026. This is an independent diagnostic; it does not select the team's final topic. Existing study directories, source volumes and policies remain frozen.

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

Pending. Commands, source/build/input/output SHA256, status/runtime, old-measurement equivalence, raw inventories and limitations will be added after execution. Publication and common PR/Release records belong to the parent chat.
