# CUBIC before a predicted route shortening: diagnostic gate

Status: declared before the new shared 100-Mbit/s baseline. No controller or simulation has been launched by this track. This is an independent diagnostic, not a team topic decision.

The question is whether a natural supplied route shortening compresses traffic arrivals enough to produce a localized queue surge and actual packet drops, and whether a small opt-in adjustment to new sending could reduce that cost. A smaller propagation BDP alone is not evidence of overflow. Already transmitted data cannot be recalled by lowering cwnd, and a queue/drop episode must be distinguished from route-induced reordering and its recovery response.

## Inputs and shared baseline

Read the existing canonical CUBIC/SACK/PRR evidence at 10 Mbit/s with 100- and 75-packet queues, plus the retained 100-Mbit/s, 1,000-packet, 40-second baseline. The original 26.2-second episode establishes received-original/spurious recovery and records no data or ACK drop in 26.1–26.6 seconds; it does not already establish shortening-induced queue overflow. The older raw traces did not include per-packet device queue sojourn measurements.

The parallel `orbit-cubic-up` diagnostic owns one fresh official 100-Mbit/s, 100-packet, 200-second CUBIC passive baseline and will share its immutable source, command, raw trace and manifest. This track will reuse that baseline instead of launching a duplicate. First simulation awaits the parent's shared declaration commit. Existing course Seoul–London state and 100-ms route updates are retained; no new topology, synthetic route jump, outage, capacity change or parameter sweep is added.

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

The fresh shared 100-Mbit/s q100 measurement is pending. No policy, improvement, or pure-shortening overflow cause is claimed.
