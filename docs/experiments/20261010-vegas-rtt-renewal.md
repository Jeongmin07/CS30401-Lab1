# Vegas RTT-reference renewal: mechanism and matched controls

**Status: implementation, ten matched simulations, cross-analysis, fresh replay and raw publication verified; ready for teammate review, 2026-10-10.** Owner: kim-seongchan with AI assistance. [PR14](https://github.com/Jeongmin07/CS30401-Lab1/pull/14), branch `experiment/vegas-rtt-renewal`, starts from latest main `b60e8e019053c7d33b853510ec06c3d94ee78faf`. The user requested continuation after [PR13](https://github.com/Jeongmin07/CS30401-Lab1/pull/13) screened Vegas's propagation/congestion confusion. This branch references that evidence without modifying its runs or assuming teammate approval.

## Research question and finding

Can a small endpoint-only update to Vegas's RTT reference recover delivery when propagation delay grows, and what happens if sustained congestion produces the same signal?

The supplied single-flow LEO case improves from **41.5113384 to 69.3432336 Mbps** of receiver application delivery over 200 s (**+67.0465%**, +695,797,380 bytes). A synthetic +6-ms RTT step has a similar mechanism and large benefit, while the fixed solo control is byte-identical with renewal off/on.

It is **not a generally safe way to distinguish route changes from congestion**. A fixed propagation path with CUBIC competition triggers 28 renewals, absorbing real queue delay into the reference. Competition shows increased Vegas share and fairness, a small aggregate benefit, and queue/loss costs that depend on the evaluation window. These data support a bounded evaluation of reference renewal in the course model; selecting it for the team report remains open.

## Actual policy and mechanism

The opt-in `RecentMinRenewal` policy retains the existing socket SRTT input and ordinary downward lifetime minimum. At a completed Vegas cycle, if Vegas is enabled, the current TCP state is CA_OPEN, cwnd is at least the pre-decision ssthresh, and more than two valid SRTT samples exist, the cycle minimum joins a bounded history. After **20 valid ACK-boundary cycles**, raise the reference to the history minimum only when it exceeds the existing reference by at least **1 ms**, then clear history. Include the current cycle to preserve `reference <= cycle minimum`. Invalid cycles and disable/enable clear history. Retain the original startup/loss-recovery rules and +/-1-MSS CA decision; no direct cwnd boost, route notification or extra protocol messages is added.

The constants were declared before the v1 matrix and are exploratory, not optimized. Twenty cycles are not exactly twenty RTTs, packets or independent samples. The actual history span is traced. Implementation state needs at most 20 history entries per socket; instrumentation I/O and simulated wall time are not a measured deployment cost.

The independent internal audit reconstructed all 21,865 Vegas trace rows across ten cases: valid-cycle gates, history minima/length/time, clearing, reference bound, diff and counts all agreed. It also compared 59 pre-first-renewal measurement trace prefixes across the five off/on pairs, all identical; fixed with no renewal uses the whole trace. [Independent audit script](../../code/vegas-study/audit_mechanism.py), [full audit result](../../code/vegas-study/evidence/mechanism-audit.json) and [execution/hash receipt](../../code/vegas-study/evidence/mechanism-execution.json) are separately preserved post-hoc artifacts. Its descriptive dequeues do not join every SRTT sample to a packet or prove continuous occupancy by themselves. This is an AI-assisted local audit, **not review by another human teammate**.

| Case | Direct internal evidence |
| --- | --- |
| Fixed solo | No renewals. Existing measurement CSVs match off/on. |
| Step solo | Traces agree before the 100-s change. Renewals at 101.995267360 s (90 -> 93.228325 ms) and 103.916500960 s (-> 96.161311 ms); each history spans 1.825229280 s. The first includes transitional SRTT, not a clean new propagation floor. |
| LEO | Renewals at 2.295799001, 123.587694999 and 189.548914666 s. First change 98.250000 -> 100.177877 ms is early CA, before the major route events; it changes diff 2 -> 1 and increases cwnd 36 -> 37 MSS while baseline holds 36. |
| Fixed competition | First renewal 91.958450720 s occurs after CUBIC starts at 80 s and before the 100-s no-op. Propagation RTT stays 90 ms. Maximum renewed reference reaches 99.452851 ms. |
| Step competition | 22 renewals, including one before the propagation step. Maximum renewed reference is 106.000245 ms while post-step propagation RTT is 96 ms. |

The supplied path truth rises from 87.507 to 90.568 ms at 121.6 s, and from 90.657 to 97.888 ms at 187.4 s. The nearby renewal reference values (91.686678 and 99.266468 ms) are SRTT-derived, not geometric propagation or directly measured LEO queue delay. About **18.27% of the total extra bytes are already delivered before 121.6 s**; whole-run gain cannot all be attributed to the two later route events. Slow-start code is unchanged, but complete early-run behavior is not identical after the initial CA renewal.

## Matched setup and receiver delivery

All ten runs use the same compiled code, patch and image, varying only declared network condition and renewal off/on. Source commit is **`82ad34a975d4b15f8a536527f8ea4f0cf6e41624`**. Each lasts 200 s, uses seed 123456789/run 1, 100-Mbit/s links, queue 100, MSS 1380, initial cwnd 10, 32-MiB buffers and a 100-GB request per flow. LEO uses unchanged supplied Seoul 1584 -> London 1585 state (100-ms routing updates, ISL/GSL), one Vegas flow, official defaults. It does not add radio losses, outages or capacity changes.

The separate micro topology is two nodes and one full-duplex point-to-point link. Pure propagation RTT is 90 ms, either fixed or raised to 96 ms at 100 s. Micro initial ssthresh is 900 MSS; root queue discs are removed and checked absent. CUBIC competition starts at 80 s on the same forward device FIFO; actual socket type and destination port are checked. The new driver preserves fractional milliseconds, unlike the earlier pilot's truncating `MilliSeconds(double)` call. The compatibility case matches that pilot's **actual** 90 -> 96 ms, not its nominal 97-ms label.

| Solo case, common window | Baseline Mbps | Renewal Mbps |
| --- | ---: | ---: |
| Fixed, whole 0–200 s | 56.2704384 | 56.2704384 |
| +6-ms RTT step, whole 0–200 s | 33.8117112 | 68.3845752 |
| Supplied LEO, whole 0–200 s | 41.5113384 | 69.3432336 |
| LEO, final 180–200 s | 8.763552 | 76.663416 |
| LEO, 101.6–121.6 s | 93.954264 | 95.680920 |
| LEO, 131.6–151.6 s | 43.743792 | 87.333576 |
| LEO, 167.4–187.4 s | 13.236960 | 96.095472 |
| LEO, 197.4–200 s (**2.6 s only**) | 3.312000 | 65.0468308 |

These are unique ordered `HandleRead` payload bytes divided by exact common half-open observation duration. Whole includes startup. The final route-event window is clipped by the 200-s state horizon and is not a 20-s steady-state test. Fixed renewal does not change the run, while the step case's raised reference changes Vegas CA decisions and can exceed fixed throughput; do not interpret every extra byte as compensation of exactly 6 ms of propagation alone.

## Genuine congestion counterexample and cost

First false-renewal history **[90.194745440,91.958450720)** has the same app/queue observations in fixed competition baseline and renewal. Actual forward FIFO time-mean occupancy is 25.60749 packets, maximum 49. For 15,374 dequeued packets, wait is minimum 0.96864, mean 2.929543, p95 5.21328, maximum 5.55744 ms. All 8,808 Vegas-tagged dequeues wait more than 1 ms. There are no observed drops **in this history window**. Raising the reference from 90 to 91.030581 ms therefore also happens under sustained real queueing without a propagation change. Positive dequeue samples alone do not establish that the queue never emptied at every instant.

At the fixed competition maximum-reference renewal, its history [179.640105440,181.546637120) contains 3,636 Vegas forward dequeues, all positive wait: minimum 9.228480, mean 10.290870, maximum 11.408160 ms. The reference reaches 99.452851 ms while propagation remains 90 ms. These direct queue records establish absorption more strongly than inferring queueing by subtracting geometric delay from sender SRTT. They characterize these windows, not all dequeues over the run.

| Common competition 80–200 s (120 s) | Fixed baseline | Fixed renewal | Step baseline | Step renewal |
| --- | ---: | ---: | ---: | ---: |
| Vegas application Mbps | 37.343260 | 38.419844 | 19.531968 | 37.045180 |
| CUBIC application Mbps | 55.940140 | 55.382896 | 72.755992 | 56.053208 |
| Aggregate application Mbps | 93.283400 | 93.802740 | 92.287960 | 93.098388 |
| Jain fairness, same window | 0.961775 | 0.968333 | 0.750411 | 0.959982 |
| Forward queue packet-mean wait, ms | 4.034803 | 4.723997 | 3.847877 | 4.434010 |
| Time-mean forward occupancy, packets | 34.0948 | 40.1453 | 32.1705 | 37.3979 |

This is a tradeoff, not evidence that fairness always worsens. Step aggregate gain over the common competition interval is only **0.878%**, even though Vegas itself gains strongly, because CUBIC receives less. In step late20, aggregate improves 92.466072 -> 94.830840 Mbps and Jain 0.526680 -> 0.731277, while queue mean wait rises 5.416850 -> 7.006251 ms and TcDrop rows rise **3 -> 11** (Vegas 0 -> 7; CUBIC 3 -> 4). In fixed late20, queue mean wait instead falls 7.663864 -> 6.320493 ms. Results vary by window; selective late metrics cannot stand in for the whole common interval.

The device queue records DropBefore/After=0, but **the full competition runs are not lossless**: total TcDrop rows are fixed baseline/renewal 204/186, step baseline/renewal 189/199. In ns-3.48 without a root qdisc, `TrafficControlLayer::Send` drops while the device transmission queue is stopped, before queue admission. Its TcDrop hook uses a sentinel device index; the two-node topology identifies the sole forward egress separately. These are genuine congestion losses, not an injected error model. Distinct tagged transmission drops, retransmissions and TCP recovery entries are recorded separately; do not equate every trace layer row with a unique physical loss, or CA_LOSS with an RTO.

## Reproduction and evidence

Use the [README](../../code/vegas-study/README.md) for complete/incremental patch selection and fresh Docker commands. The complete patch was generated with the official `make_patch.sh`, SHA256 **`25ac4286f68373ee4e33d43f5f00e8676a65fc9c8747d65f643cd0fc28202f59`**. Official image:

```text
ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4
```

Primary container `lab1-vegas-20261010`, separately initialized volume `cs30401-vegas-ns3-20261010`. The ten-case matrix was declared before launch; all exited zero. Two concurrent workers took **299.778 s** for the matrix; per-simulation times ranged **14.313–164.348 s**. Wall times include machine load and detailed observation I/O; they are not cross-machine benchmarks. Every case preserves exact command, settings, source/patch/binary/all-shared-library hashes, policy and actual runtime.

[Compatibility hashes](../../code/vegas-study/evidence/compatibility.json) establish **27 existing measurement CSVs byte-identical**: 18 from two original 20-s fixed/step controls at launch `fb1385223a85d0eef9d9e79f314b408b9b17e139`, plus nine supplied 200-s LEO baseline CSVs versus PR13. Wall-clock timing is excluded; internal Vegas/queue records are additional outputs. The fixed 200-s off/on pair also has nine existing measurement CSVs identical. Original raw records were not edited or labeled as new code results.

The original analyzer and the new independent analyzer are both run on fresh post-hoc output paths. They check app sums/bins, actual micro socket/delay settings, queue conservation/coverage/occupancy and state gates. Analysis helper/source commit is distinct from the preserved simulation launch commit. Full analysis outputs and packet logs remain outside Git; small summaries, tables, input hashes and execution receipts are committed.

All **10/10** full analyses passed, taking **376.085289 s** with two workers. Original-analyzer app totals/goodput/bins agree with the independent sums for every case. All currently present declared source/binary/library artifacts match their simulation-launch hashes. Post-hoc analysis checkout `21f828aabd1cd15b6912de65cf96342a437ff1a9` was clean; export helper is `a75c7f41cd76d230022a666edc05685064bc7384`. [Analysis matrix](../../code/vegas-study/evidence/analysis-matrix.json) preserves commands, console references and per-phase source/runtime; [export receipt](../../code/vegas-study/evidence/export.json) identifies the separate export. Compact [results](../../code/vegas-study/evidence/results.csv), [actual queue sojourn](../../code/vegas-study/evidence/queue_sojourn.csv) and [renewals](../../code/vegas-study/evidence/renewals.csv) have 72, 174 and 55 rows. Every case has original settings/launch manifest and a small source-backed summary under `code/vegas-study/evidence/cases/`.

A second newly initialized official volume/container applied only the complete patch to pristine `cs30401-base`, built successfully in 45.732 s, and replayed fixed-competition renewal plus LEO baseline/renewal at the immutable launch commit. **3/3 runs exited zero; all 48 compared measurement CSVs matched original size and SHA256 exactly.** Executables, shared libraries, patch and source identities also matched. LEO wall-clock timing CSVs differed as expected and were excluded from the measurement verdict. Actual simulation wall times were 30.271, 84.064 and 161.721 s; the two-worker replay batch took 192.828 s. This is deterministic reproducibility, not three additional statistical seeds. [Comparison](../../code/vegas-study/evidence/replay-comparison.json), [preparation](../../code/vegas-study/evidence/replay-preparation.json) and [receipt](../../code/vegas-study/evidence/replay-records.json) preserve successful checks and the initial local-clone ownership failures/repaired setup. Host Git settings and prior studies were not changed.

The [raw release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-renewal-20261010) contains 12 original primary run trees (ten matrix cases plus two compatibility controls), the simulation matrix, full analyses/console receipts and fresh-replay build/preparation/hash records. It excludes state, ns-3 source/builds and binaries; identical fresh-replay raw CSVs are represented by their comparisons rather than duplicated. All **380** archive members were independently streamed and checked against original size/SHA256, and the copied host archive was hashed again. [Archive verification receipt](../../code/vegas-study/evidence/raw-archive-receipt.json):

```text
cs30401-vegas-raw-20261010.tar.gz
1,373,614,586 bytes (7,545,357,481 original bytes)
SHA256 5f63e78ef2eec9c5206b16185c9595617d54257a836863b8139367c9eea77723
Inventory SHA256 5e4ed2b68907368afadb4d299bd81239313bfd6ba39876dac2a79e0764fbfa27
```

The per-file inventory is both embedded and supplied separately. The release tag targets simulation launch `82ad34a`, not the later analysis/documentation checkout. After publication, both GitHub asset states/sizes/SHA256 digests matched the local archive and inventory; [publication receipt](../../code/vegas-study/evidence/raw-publication.json) links the downloadable assets. The small Git evidence plus verification records total about 0.8 MB; no large original CSV was committed. The independent mechanism audit was written after this raw archive and is separately supplied in Git, not relabeled as one of the archive's 380 members. Prior PR13 originals remain in its separate release and were not moved or overwritten.

## Prior work and scope

[La, Walrand and Anantharam, *Issues in TCP Vegas* (1999), §§3–4](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1999/Archive/ERL-99-3.pdf) describe sustained RTT-minimum increases as a rerouting signal and the persistent-congestion ambiguity. Our policy is a simplified ns-3-specific adaptation: SRTT minima per valid cycle, a 20-cycle history and 1-ms gate, without their full initialization/threshold/window-rescale mechanism. It is not claimed as their exact implementation or a new invention.

[Gu and Zhang, *Behavior and performance improvement of TCP Vegas in LEO satellite networks* (2005), DOI 10.1109/WCNM.2005.1544194](https://pure.bit.edu.cn/en/publications/behavior-and-performance-improvement-of-tcp-vegas-in-leo-satellit/) directly studies Vegas's path-change misclassification. Only institutional abstract/metadata were accessible here; its full method and experimental conditions have not been read or reproduced. The proposed contribution is the mechanism and measured benefit/cost boundary in the course model.

One fixed seed on one supplied route and these micro controls supports a deterministic case study, not statistical confidence, a universal safety claim or all real LEO networks. No LEO multi-flow/per-hop queue experiment, parameter sweep, receiver-side reference probing or noisy route-notification transport is implemented. A future attempt to prevent queue absorption needs additional evidence or probing and its explicit cost, not a fabricated perfect route signal. Final team topic, combined report, names and merge remain decisions for the three teammates. Other AIs should assess these concrete records rather than assume agreement from this PR.
