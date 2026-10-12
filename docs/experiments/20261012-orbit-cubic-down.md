# CUBIC before a predicted route shortening: diagnostic gate

Status: diagnostic gate completed and candidate screened out within the declared budget, 12 October 2026. The plan was declared before the shared runs. No active controller, candidate ON run or separate simulator container was launched by this track. This is an independent diagnostic, not a team topic decision.

The question is whether a natural supplied route shortening compresses traffic arrivals enough to produce a localized queue surge and actual packet drops, and whether a small opt-in adjustment to new sending could reduce that cost. A smaller propagation BDP alone is not evidence of overflow. Already transmitted data cannot be recalled by lowering cwnd, and a queue/drop episode must be distinguished from route-induced reordering and its recovery response.

## Inputs and shared baseline

Read the existing canonical CUBIC/SACK/PRR evidence at 10 Mbit/s with 100- and 75-packet queues, plus the retained 100-Mbit/s, 1,000-packet, 40-second baseline. The original 26.2-second episode establishes received-original/spurious recovery and records no data or ACK drop in 26.1–26.6 seconds; it does not already establish shortening-induced queue overflow. The older raw traces did not include per-packet device queue sojourn measurements.

The parallel `orbit-cubic-up` diagnostic owns the fresh official passive baseline and shared immutable source, command, raw trace and manifest. This track reused its successful 10-Mbit/s observation and preserved the failed 100-Mbit/s attempt instead of launching duplicates. Shared declaration commit `58e51e3bd73076eb9a03efa7d9b829b8ef6fe79f` preceded both launches; prepared diagnostic code was subsequently committed as `efdc735a81aebbf454e1b23f5fcad9aaf8f39a5a`. Existing course Seoul–London state and 100-ms route updates are retained; no new topology, synthetic route jump, outage, capacity change or parameter sweep is added.

## Declared observation windows and gate

Select only supplied `path_changed` transitions whose propagation RTT falls; enumerate them from `code/kim-study/path_truth_200s.csv` before examining the new baseline. The known transitions are 26.2 and 75.0 seconds. For each event T, use `[T-0.5,T)` and `[T,T+0.5)` as equal-width pre/post diagnostic windows, and the existing `[T-0.5,T+2)` window for legacy context. Also inspect the existing 100-ms event-adjacent bins, retaining exact packet/drop times.

Keep device identity and direction rather than averaging all devices. Record source-device and changed-route queue enqueue/dequeue/drop counts, pending and packet-weighted served sojourn, exact tagged TcDrop/device-drop time, flow0 new TX and retransmission, wire Rx ordering, ordered application bytes, cwnd/inflight and congestion state. Queue visit means are not end-to-end queue delay, and occupancy recorded at a flush event is not automatically a bin-boundary snapshot. Root queue-disc/drop coverage determines the strength of absence-of-drop claims.

Advance only if a natural shortening has a temporally localized, same-device queue/arrival-compression and actual drop episode that cannot reasonably be accounted for solely by baseline congestion trajectory, delayed ACKs, reordering or recovery. A larger post-event drop count alone is insufficient for causal attribution. The fresh baseline is observational and cannot by itself isolate every effect of a complete route replacement.

If the required phenomenon is absent or attribution remains weak, stop without implementing a policy and report the measured counterevidence and unresolved limits. Do not widen the event, inflate RTT changes or sweep traffic settings until a favorable result appears.

## Conditional implementation and bounded evaluation

Only after that gate and a recorded source review, consider one opt-in CUBIC geometric-BDP reduction or temporary new-data pacing adjustment in a separately owned official volume. The operator supplies a forecast of the route event and old/new propagation RTT; it does not provide future queue occupancy or TCP outcomes. Preserve existing loss recovery and explain why sending less cannot remove traffic already in flight.

At most one matched baseline/candidate LEO comparison and, if implemented, one finite genuine-loss micro control are added. Container limit: two CPUs, 4 GiB, build with one job, 240-second wall cap per simulation. No further benchmark matrix or topology exploration is authorized for this diagnostic. Preserve observer-off equivalence, exact source/patch/binary/library/input/output hashes, command, runtime, status and actual policy action count. A source-only feasibility argument does not replace inspection of the shared measured baseline.

## Existing evidence inspected before the shared baseline

The supplied path table has exactly two route-changing RTT decreases: 26.2 s (97.698 to 91.064 ms) and 75.0 s (90.987 to 87.644 ms). Their geometric new/old BDP ratios are about 0.9321 and 0.9633. These ratios are not measured queue surplus or required cwnd reductions.

`analyze_gate.py` read the retained raw baseline CSVs, verified available original output hashes, and computed the predeclared half-open windows. It is a posthoc extractor only, with no simulator or controller invocation. Sources and exact numbers are preserved in [`existing-summary.json`](assets/20261012-orbit-cubic-down/existing-summary.json) and the linked raw diagnostic JSONs.

| Existing run | Event | All-direction drop rows in pre/post/legacy windows | Post-window retransmissions | Legacy application goodput |
| --- | --- | --- | --- | --- |
| 10 Mbit/s, q100, 200 s | 26.2 s | 0 / 0 / 0 | 3 | 9.485568 Mbit/s |
| 10 Mbit/s, q100, 200 s | 75.0 s | 0 / 0 / 0 | 0 | 9.626880 Mbit/s |
| 100 Mbit/s, q1000, 40 s | 26.2 s | 0 / 0 / 0 | 32 | 96.092160 Mbit/s |

Thus the inspected event traces provide no actual overflow drop to prevent; retransmission counts alone do not change that. Their per-device queue sojourn was not recorded, so queue occupancy or compression itself remains unmeasured rather than zero. The existing q75 compact baseline reports two retransmissions near 26.2 s and 11 near 75 s, but only a whole-run drop count of 440; this track has not read q75 local raw drop times and cannot attribute those losses to shortening.

## Shared passive observation and decision

The fresh shared 10-Mbit/s q100 simulation completed successfully in **29.240159211 wall seconds**. Eight canonical measurement CSVs match the original reference by byte/SHA comparison in the owner's [`equivalence10.json`](assets/20261012-orbit-cubic-up/equivalence10.json). This one-condition check supports the passive instrumentation here; it is not universal equivalence across rates or policies. Launch patch SHA is `910aac06723fac851e46eb6522146d896a433a04b3a8464d46e5c4c72ff8fc78`, and runtime binary/libraries were unchanged after both attempts. The source files were uncommitted at launch; the per-run hashes, rather than a falsely clean Git commit claim, identify them.

Actual queue visits are nonzero. The source device is node 1584/device 1; below are flow0-tagged, served packet visits in the equal-width pre/post windows. They include zero waits, not end-to-end delay or every unserved packet.

| Event | Source mean queue visit, pre → post | Source maximum visit, pre → post | Additional observation | Actual drop rows, pre/post/legacy |
| --- | --- | --- | --- | --- |
| 26.2 s | 19.232893 → 10.015434 ms | 21.830038 → 26.380293 ms | Node 313/device 1 has post maximum 6.017616 ms; source delivery/recovery trajectory changes | 0 / 0 / 0 |
| 75.0 s | 48.901616 → 59.623105 ms | 53.891492 → 65.884991 ms | Source queue grows, without retransmission in the post/legacy windows | 0 / 0 / 0 |

Whole-run queue QA passes for 74 device/flow groups: enqueued minus dequeued equals terminal pending, every dequeued visit has a sojourn sample, and DropAfterDequeue is zero. Terminal pending is **26 packets**, as expected for an unfinished bulk flow at the simulation cutoff; no finite completion or zero-backlog claim is made. Sources: [`shared-cubic10-gate.json`](assets/20261012-orbit-cubic-down/shared-cubic10-gate.json) and [`queue conservation receipt`](assets/20261012-orbit-cubic-down/shared-cubic10-queue-conservation.json). The window drop-zero statement is limited to the connected observed hooks and declared intervals, not the entire run.

The shared 100-Mbit/s q100, 200-second attempt reached its **240-second wall cap** (actual **240.101341081 s**) and has manifest status `timeout`, exit code `null`. Its 20 existing output files match the failed manifest's hashes and are preserved. Those hashes establish preservation, not complete CSV formatting, final flush, queue conservation, 200-second goodput or a valid baseline comparison. [`shared-cubic100-incomplete.json`](assets/20261012-orbit-cubic-down/shared-cubic100-incomplete.json) records source/runtime/input/output identities and this boundary. The analyzer rejects that manifest before creating a normal result. No partial prefix is turned into a performance comparison, and no rerun or longer cap is requested.

**Decision: stop before active cwnd drain/pacing implementation.** The completed conditions show queue changes and, at 26.2 s, unnecessary recovery, but no local actual drop to prevent. The faster small-queue condition remains unverified because its run did not complete. This means shortening-induced overflow and a benefit from the proposed proactive drain are not established; it does not mean queues never grow, or that overflow is impossible in other conditions. Lowering a window still cannot recall data already sent. No ON run, genuine-loss micro, sweep or new topology is justified within this gate. [`decision.json`](assets/20261012-orbit-cubic-down/decision.json) preserves the conclusion and numeric inputs.

## Commands and preservation scope

The completed source-backed extractions were:

```text
docker exec lab1-predict-loss-20261012 python3 -B /work/code/orbit-cubic-down/analyze_gate.py --run /tmp/predict-loss/leo10-base --path-truth /work/code/kim-study/path_truth_200s.csv --out /work/docs/experiments/assets/20261012-orbit-cubic-down/existing-leo10-base.json
docker exec lab1-predict-loss-20261012 python3 -B /work/code/orbit-cubic-down/analyze_gate.py --run /tmp/predict-loss/leo100-base40 --path-truth /work/code/kim-study/path_truth_200s.csv --out /work/docs/experiments/assets/20261012-orbit-cubic-down/existing-leo100-base40.json
docker exec lab1-orbit-cubic-up-20261012 python3 -B /work/code/orbit-cubic-down/analyze_gate.py --run /tmp/orbit-cubic-up/cubic10-observed200 --path-truth /work/code/kim-study/path_truth_200s.csv --out /work/docs/experiments/assets/20261012-orbit-cubic-down/shared-cubic10-gate.json
```

The same command directed at `cubic100-observed200` fails with `Incomplete or failed run` and creates no `shared-cubic100-gate.json`. The queue CSV argument is optional when exactly one `*queue_bins.csv` is present. Existing output paths are refused. Raw files and original manifests were read only; compact SHA receipts remain in this track, and raw/source sharing belongs to the owning `orbit-cubic-up` record. This diagnostic has no active ns-3 patch or claimed controller action count.
