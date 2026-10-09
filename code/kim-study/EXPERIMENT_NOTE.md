# TCP Reordering Protection in the Course LEO Model

**Independent exploratory work by kim-seongchan with GPT assistance.** This note records 23 distinct completed configurations: the 20-case version 4 matrix, two version 5 short-flow controls, and one version 5 routing-timing control. Teammates' results are excluded. These deterministic configurations are not repeated-seed statistical samples, and this is not an agreed team research decision.

The main finding is narrow: in the tested ns-3 CUBIC/SACK/PRR stack, a route change can produce recovery after the missing original segment has already been accepted by the receiver. Temporarily increasing reordering tolerance prevents that event, but whole-run throughput gains are small, some conditions worsen, and genuine short-flow loss can incur a large completion-time penalty. This supports a mechanism study with explicit counterexamples, not a general claim that the proposed controller improves LEO TCP.

## Environment and measurement

The official image is `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1`, digest `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`; environment source commit `f77e9a6a850805741d7290913c88ffe43dcae4ca`. Independent containers and ns-3 volumes were used. The baseline has ns-3.48 and the course Hypatia modules, Starlink shell 1, Seoul–London traffic, 100-ms routing updates, equal ISL/GSL rates, and drop-tail device queues. Default TCP settings include 1,380-byte segments, initial cwnd 10 segments and 32-MiB buffers. These runs add no LEO handover interruption, varying capacity or random radio loss.

The 10/100-Mbit/s rates and 50/100/1,000-packet queues are exploratory operating conditions, not measurements of deployed Starlink. The 100-Mbit/s point-to-point controls use 2,000-packet queues and initial ssthresh 900 segments, approximately one 100-ms bandwidth-delay product. The delay-step changes one-way propagation from 50 to 45 ms at 10 seconds. Stable controls keep it at 50 ms. Genuine-loss controls discard exactly one data packet at or after the specified time; ordinary congestion losses can also occur in the bulk-flow cases.

Goodput means unique application bytes delivered at the receiver divided by the full simulated duration. Wire payload counts and sender ACK progress are separate metrics. Event comparisons use fixed windows from 0.5 seconds before to 2 seconds after the marker. Sender smoothed RTT is time-weighted between trace changes; it is not raw packet RTT or isolated queueing delay.

Custom `flow_id`/`tx_id`/`tx_time_ns` tags join particular transmissions across sender, receiver and drop traces. Packet UID alone is insufficient. A wire arrival before TCP processing is not treated as accepted delivery without matching-time application delivery or subsequent expected-sequence advancement. Queue, IP, device and traffic-control drop hooks are connected, and root queue-disc absence is checked per device. The final LEO manifests contain 50,704 successful checks; point-to-point manifests contain 16. Earlier microbenchmark prototypes with an automatic FqCoDel root queue disc are excluded from loss-exclusion claims.

## Mechanism established in the baseline

At the 26.2-second Seoul–London transition, propagation RTT decreases by 6.634 ms. The 10-Mbit/s baseline shows five out-of-order payload arrivals. Original transmission 21,859, sequence 29,734,861, is accepted at **26.283909347 seconds** with same-time application delivery. The sender nevertheless retransmits that range and enters `CA_RECOVERY` at **26.328788841 seconds**. No matching actual drop is observed. ACK/SACK, sequence and state evidence establish this episode; a cwnd reduction alone would not.

The prototype changes `ReTxThreshold` from its default 3 to a larger value during notified windows, then restores it when the socket state permits. For the 10-Mbit/s tests, windows are 26.1–26.5 and 74.9–75.3 seconds. Raising the threshold does not clear losses already marked in the SACK scoreboard, so activation timing matters. Deferring restoration can extend the actual protected interval.

Threshold 20 preserves the same original delivery while removing the first event's three retransmissions and recovery entry. Goodput over 25.7–28.2 seconds increases from **9.485568 to 9.622464 Mbit/s**, approximately **1.44%**. Whole-run goodput increases only about **0.023%**. At 75 seconds, the 10-Mbit/s baseline has one reordered packet without unnecessary recovery; a route change does not invariably cause a harmful response.

The immediate trigger is **SACK packet-count loss marking**, not three consecutive duplicate ACKs. At 26.328788841 seconds, ACK packet 42,007 carries cumulative ACK 29,734,861 and SACK range 29,739,001–29,743,141: three segments above the hole. The sender enters recovery and retransmits at that timestamp. ACK packet 42,009, acknowledging through 29,736,241, arrives at 26.329936038 seconds, **1.147197 ms later**. The original segment was accepted at the receiver earlier, but its covering ACK had not yet reached the sender. No observed data or ACK drops occur in 26.1–26.6 seconds. See the [source-row evidence excerpt](evidence/event26_evidence.csv).

Retaining the prior forwarding snapshot removes this episode with the same binary and flow schedule. This supports a routing-transition cause. The control changes the complete forwarding snapshot, and live per-hop packet paths were not traced; it does not isolate propagation-delay shortening from every new-path queue/link effect.

## Complete configuration results

The first 20 rows are version 4. The final three are version 5. Goodput is rounded here; analysis JSON retains more precision. “Drops” counts distinct tagged transmissions with observed drops, not summed hook rows. “Retx” counts the official sender retransmission trace. All LEO cases use CUBIC except the named Vegas and BBR probes; all micro cases use CUBIC.

| Case | Duration s | Goodput Mbit/s | Drops | Retx |
| --- | ---: | ---: | ---: | ---: |
| leo10-base | 200 | 9.544356 | 499 | 523 |
| leo10-static20 | 200 | 9.546950 | 476 | 495 |
| leo10-guard20 | 200 | 9.546509 | 486 | 507 |
| leo10-late20 | 200 | 9.544356 | 499 | 523 |
| leo10-guard8 | 200 | 9.546509 | 486 | 507 |
| leo10-guard32 | 200 | 9.546509 | 486 | 507 |
| leo100-base | 85 | 95.416382 | 320 | 367 |
| leo100-static64 | 85 | 95.422487 | 327 | 327 |
| leo100-guard64 | 85 | 95.422487 | 332 | 332 |
| leo10-smallq-base | 200 | 9.178270 | 305 | 329 |
| leo10-smallq-guard20 | 200 | 9.144708 | 303 | 326 |
| leo10-vegas | 200 | 1.918200 | 0 | 0 |
| leo10-bbr | 200 | 9.318202 | 835 | 842 |
| micro-step-base | 20 | 92.772984 | 144 | 185 |
| micro-step-static64 | 20 | 92.795616 | 170 | 170 |
| micro-step-guard64 | 20 | 92.795616 | 170 | 170 |
| micro-stable-base | 20 | 92.771328 | 163 | 163 |
| micro-loss-base | 20 | 92.770776 | 145 | 145 |
| micro-loss-static64 | 20 | 92.770776 | 145 | 145 |
| micro-loss-guard64 | 20 | 92.770776 | 145 | 145 |
| micro-tail-base-v5 | 4 | 0.055200 | 1 | 1 |
| micro-tail-guard20-v5 | 4 | 0.055200 | 1 | 1 |
| leo-delay26-base-v5 | 200 | 9.546509 | 471 | 496 |

### Benefits do not hold uniformly

Thresholds 8, 20 and 32 have identical outcomes in the tested 10-Mbit/s scenario; this does not establish a universal optimum. Late windows starting at 26.4 and 75.2 seconds reproduce the default result. At 100 Mbit/s, static and notified threshold 64 both remove observed reordering-related retransmissions, but whole-run improvement is only **0.0064%**.

With 50-packet queues, first-event goodput increases from 8.884992 to 9.560640 Mbit/s, while whole-run goodput decreases about **0.366%**. In the point-to-point delay-step case, protection removes the reordering recovery but subsequent genuine congestion changes the trajectory: 9.5–12-second goodput falls from 96.246720 to 87.993216 Mbit/s. A local recovery reduction is not sufficient to claim overall benefit.

Time-weighted mean SRTT in the 10-Mbit/s baseline is 148.13 ms, compared with 151.19 ms under notified protection and 154.95 ms under continuous threshold 20. These are measured tradeoffs in the evolving system, not proof that the threshold directly adds a fixed amount of queueing.

## Genuine-loss counterexamples

In the stable bulk-flow control, the same original transmission is dropped at 10.060109600 seconds. Both larger-threshold variants delay its first retransmission and validated gap repair by 6.99792 ms, despite identical whole-run goodput.

| After the same actual drop | Default 3 | Static or notified 64 |
| --- | ---: | ---: |
| First retransmission delay ms | 50.34912 | 57.34704 |
| Accepted gap-repair delay ms | 306.64656 | 313.64448 |

Notified protection actually lasts 9.99–10.4237584 seconds, beyond its requested 10.3-second end. Unsafe-state restoration deferral is part of the cost.

The short-flow controls send 27,600 bytes on a stable 50-ms one-way path and drop the first data segment once. The case names contain “tail,” but the dropped packet is not the last segment. Default TCP completes application delivery at **0.251509920 seconds**; protection at threshold 20 completes at **1.150124001 seconds**, about **4.57 times later**. Only 19 repeated ACKs arrive, so the larger threshold prevents fast recovery and the flow enters the timeout/`CA_LOSS` path. Restoration is deferred until 1.100009281 seconds. Identical four-second average goodput hides this application-visible penalty.

## Routing-timing diagnostic control

The control reuses the 26.1-second forwarding snapshot at updates 26.2 through 26.8 seconds, then resumes the current snapshot at 26.9 seconds. Satellite movement and geometric propagation continue. It is not a static-distance path or a proposed deployable routing policy.

No out-of-order arrival or recovery occurs around either 26.2 or the resumed 26.9-second transition. Whole-run goodput is 9.5465088 Mbit/s. This supports dependence on route timing and the packets then in flight; delaying an event does not guarantee reproducing its original reordering. It also changes later dynamics, so whole-run equality with the protected variant does not make the two mechanisms equivalent.

## Scope, prior work and reproduction

CUBIC is a relevant standard controller ([RFC 9438](https://www.rfc-editor.org/rfc/rfc9438.html)), but this result concerns ns-3.48's tested CUBIC/SACK/PRR stack and packet-count loss detection. The inspected implementation lacks RACK-TLP; it does not establish a defect in current Linux TCP. Reordering robustness through delayed loss detection is already described in [RFC 4653](https://www.rfc-editor.org/rfc/rfc4653.html); [RFC 8985](https://www.rfc-editor.org/rfc/rfc8985.html) specifies time-based RACK-TLP. The limited contribution under investigation is selective activation using route information and measured benefit/cost conditions, not invention of reordering protection.

The handout permits one or more problems and ideas. A second mechanism can be studied if independently validated. The Vegas throughput probe is not a demonstrated modern-TCP defect, and BBR's RTT-model staleness has not been causally established. Neither is ready to be presented as a completed improvement. Multi-flow fairness, other ground-station pairs, imperfect operator information, and comparison with implemented RACK remain open.

Artifacts include [per-case manifests and compact analysis summaries](evidence/cases), the [matrix execution record](matrix_execution.json), [analysis code](analyze_study.py), [source patch](ns3.patch), and [figure source hashes](figures/v4/figure_sources.json). The [fresh-volume reproduction record](reproduction_v4.json) verifies **one** notified-threshold LEO case, not all 23 configurations: its cwnd, smoothed RTT and sender-progress files match byte for byte.

| Reproduced legacy trace | SHA-256, original and fresh volume |
| --- | --- |
| cwnd | `acf9286c1705fa2aa31eb56805f016c3793051f3d566bc91c87c151af2c5cace` |
| RTT | `5f7ed6085a55daca60bb23bb3df73b6098d879aa2005d8810d887b023080edc7` |
| progress | `4ce98bb78f4f26fbc697971d23cfc085d8a3e89ad6b378222900a20469794ca4` |

That initial check verifies those three deterministic outputs for that case. A subsequent [complete independent-volume replay](evidence/reproduction_v5.json) uses the canonical version 5 patch and the committed configuration manifests for all 23 cases. **All 184 raw analysis/legacy trace files and all 23 full analysis JSON files match byte for byte.** These are deterministic reproduction checks, not statistical replicates. The [replayed case manifests](evidence/replay_case_manifests_v5.json) retain patch, binary and input provenance. All five figures were regenerated using `uv sync --frozen` and the README commands; identical rendered-image bytes are not claimed.

The replay volume was initialized independently from the original experiment volume. It first ran the version 4 single-case check, then that patch was reversed and the canonical version 5 patch applied before the complete replay. Source history is recorded explicitly; it is not described as an untouched volume at every stage. Receiver TCP rejection paths and incomplete packet identities are separately acknowledged by the analyzer rather than silently counted as loss-free evidence. Final submission must regenerate all reported results from code and README alone.

Related foundation: S. Kassing, D. Bhattacherjee, A. B. Aguas, J. E. Saethre and A. Singla, [“Exploring the ‘Internet from space’ with Hypatia,” ACM IMC, 2020](https://bdebopam.github.io/papers/imc2020-hypatia.pdf). Standards cited above: L. Xu, S. Ha, I. Rhee, V. Goel and L. Eggert, RFC 9438, 2023; S. Bhandarkar, A. L. N. Reddy, M. Allman and E. Blanton, RFC 4653, 2006; Y. Cheng, N. Cardwell, N. Dukkipati and P. Jha, RFC 8985, 2021.
