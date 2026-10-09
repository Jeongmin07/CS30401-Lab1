# Finite-Flow Exemption and Notification Timing: Phase Two

**Independent completed experiments by kim-seongchan with GPT assistance.** This note covers 52 phase-two case IDs, all successful, with patch version 6. They extend the initial 23 cases. These are declared deterministic runs, including regression controls that overlap earlier conditions; they are not 75 independent unique conditions or independent seed replicates. Teammates' results are excluded. This is research evidence for discussion, not an agreed team decision or a completed submission.

The main result is limited but concrete: exempting known small transfers from the high threshold removes the demonstrated 20-segment true-loss penalty by retaining baseline loss detection for those flows. It preserves the tested bulk LEO result, but does not solve longer finite-flow or final-segment loss. Separately, a controlled 80-segment delay-step case has verified unnecessary recovery and a larger completion-time benefit. Window-offset experiments demonstrate timing dependence, not a universal notification-accuracy guarantee.

## Implemented rule and assumptions

Before connection establishment, the sender computes `ceil(MaxBytes / SegmentSize)`. With `study_short_flow_cutoff_pkts=21`, a known nonzero transfer size at or below 21 nominal MSS equivalents uses threshold 3 throughout the flow. Larger transfers retain the configured threshold/window behavior. The trace records `SHORT_FLOW_GUARD_BYPASS` when the rule applies.

This is an **upfront transfer-size exemption**, not an adaptive rule based on remaining flight, current ACK opportunities, congestion window, or a detected tail. Nominal MSS equivalents are not measured on-wire packet counts. Cutoff 21 is a conservative diagnostic choice near threshold 20, not a proved optimal boundary. The added 21-segment controls verify its inclusive boundary, while 22-segment controls expose its limited scope.

Analyzer `protection_intervals` and `restore_deferrals` are generic controller-lifecycle metadata. They can include `THRESHOLD_SET` from 3 to 3 and later restoration handling in bypassed flows, although the effective threshold remains baseline 3. Those counts do not establish high-threshold exposure or a loss penalty. Effective activation must be checked against raw `THRESHOLD_SET` with `new_value > 3` and `SHORT_FLOW_GUARD_BYPASS`. The recorded metrics are unchanged; their controller-lifecycle and effective-threshold meanings are distinguished here.

The known size comes from the simulation application's `MaxBytes`. A deployment would need that information from the application or a comparable interface; ordinary open-ended TCP streams do not necessarily announce their final size. Exempt flows also give up any benefit of increased reordering tolerance. That is a policy tradeoff, not a new recovery algorithm. The 20-segment step control shows no such benefit to lose in its tested packet phase, but does not prove that all small transfers are immune to reordering.

The baseline, unqualified window protection (`guard20`), and size exemption (`exempt21`) share the same conditions. The exemption's nominal controller parameters are:

```text
study_threshold=20;study_windows=0:500000000;study_short_flow_cutoff_pkts=21
```

The tests use the same CUBIC/SACK/PRR stack without RACK-TLP. Initial environment and deployment qualifications in [PARAMETER_AND_DEPLOYMENT_NOTE.md](PARAMETER_AND_DEPLOYMENT_NOTE.md) continue to apply.

## True loss: what is repaired and what remains

All finite actual-loss cases observe exactly one intentional receive drop and one retransmission, and deliver their full configured byte count. Completion time is final unique receiver application delivery minus the zero-time application start, including connection establishment. Four-second average goodput is identical between modes of a given size and therefore hides these timing differences.

For first-segment loss in a 20-MSS transfer, unqualified protection completes at **1.150124001 s**; the exemption and baseline both complete at **0.251509920 s**. For middle loss, protection completes at **1.251165120 s**, while exemption and baseline both complete at **0.350711200 s**. Exemption also restores baseline timing for the tested four- and eight-segment first-loss transfers. At exactly 21 segments, protection takes **0.450716800 s**, and exemption restores baseline **0.350482400 s**. Its improvement follows from disabling the high threshold for these transfers, rather than making threshold 20 detect their losses faster.

With only three segments, even baseline lacks sufficient following feedback for its usual fast recovery; all modes complete at 1.150124001 s with a `CA_LOSS` entry. Last-segment loss similarly leaves the 20- and 80-segment cases on the baseline timeout path in all modes. An upfront size exemption cannot manufacture feedback after the last segment.

The cutoff leaves a clear failure immediately above its scope: with 22 segments and first-segment loss, exemption does not activate, and both protected modes take **0.450716800 s**, compared with baseline **0.350597120 s**. The 80-segment first-loss case has nearly equal completion times between modes, which does not establish equal recovery behavior in general. Reducing the threshold to 8 in the 20-segment first-loss case avoids the long timeout but still takes **0.350482400 s**, slower than baseline. Thus neither a fixed lower threshold nor cutoff 21 is a general finite-flow solution.

## Controlled finite-flow reordering

The delay-step controls change one-way channel delay from 50 to 45 ms at 0.201 s, with no intentional loss. In the 20-MSS case, all modes finish at 0.251050400 s without retransmission or recovery; that packet phase does not reproduce a harmful event.

The 80-MSS baseline finishes at **0.611527200 s**, whereas both protected variants finish at **0.430944960 s**, about **29.53% earlier**. The exemption does not apply to this size, so it retains protection. No network drop is observed under the connected drop hooks and root queue-disc absence checks. Baseline has eight retransmissions and one recovery entry; protected modes have neither.

The matched 80-MSS stable-delay, no-loss controls finish at **0.452206240 s in all three modes**, without retransmission or recovery. The delay-step baseline is slower than that stable baseline despite the shortened propagation; protected delay-step completion is faster. This distinguishes the step's geometric latency change from its harmful TCP response. The 29.53% figure compares controllers on the **same changed channel**, not the changed channel against a different stable path, and is not a general LEO throughput gain.

The publication figure `finite_delay_step` plots these six matched **80-MSS** cases only. The 20-MSS sanity controls are retained in the configuration/results table and in the discussion above; they are not a second panel in that figure.

Source-level packet/ACK/application audit establishes the mechanism. At 0.246165120 s, sequence 24,841 reaches the receiver while it expects 13,801. The eight original ranges beginning at sequences 13,801 through 23,461 are all accepted by the application at 0.250247360–0.251050400 s, before their retransmissions at 0.291399520–0.291973120 s. Sender ACK 13,801 carries progressively larger SACK blocks at 0.291170080, 0.291284800 and 0.291399520 s; the third eligible update coincides with three SACKed segments above the hole, recovery and the first retransmission. The traces do not isolate the internal duplicate-ACK versus SACK presumed-loss branch for this control; both use the packet-count threshold. The covering ACK 15,181 arrives at 0.295252320 s, 3.8528 ms later.

This is a synthetic deterministic channel control, not a measured LEO workload or a second large improvement in the full LEO run. The channel change affects both directions. A higher sequence's TCP transmission timestamp can precede 0.201 s because the trace occurs before device-queue service; that timestamp alone does not identify the propagation delay experienced by that packet. No live per-hop attribution is inferred from it. Both protected variants record `THRESHOLD_SET` from 3 to 20 without a bypass. Their socket closes before the requested 0.5-second end, so an empty completed-interval list in the analyzer is not evidence that protection never activated.

## Bulk LEO behavior and shifted windows

On the 200-second, 10-Mbit/s, 100-packet-queue Seoul–London case, both `guard20` and `exempt21` deliver **9.5465088 Mbit/s**, compared with baseline **9.544356 Mbit/s**, a **0.02256%** increase. The 100-GB transfer is above the exemption cutoff. Protection preserves the original first-event result: fixed 25.7–28.2 s application goodput increases from **9.485568 to 9.622464 Mbit/s** (**1.4432%**), and three retransmissions plus one recovery entry become zero in that window.

The windows around 26.2 and 75.0 s are both shifted by the same tested offset, keeping nominal length 0.4 s. Offset zero uses 26.1–26.5 and 74.9–75.3 s. The following table always evaluates delivery against the **true first-event window**, not a window moved to match the notice.

| Offset ms | First requested interval s | Whole-run Mbit/s | True first-event Mbit/s | First-event retx / recovery |
| ---: | --- | ---: | ---: | --- |
| -200 | 25.9–26.3 | 9.5443560 | 9.485568 | 3 / 1 |
| -100 | 26.0–26.4 | 9.5465088 | 9.622464 | 0 / 0 |
| 0 | 26.1–26.5 | 9.5465088 | 9.622464 | 0 / 0 |
| +100 | 26.2–26.6 | 9.5465088 | 9.622464 | 0 / 0 |
| +200 | 26.3–26.7 | 9.5465088 | 9.622464 | 0 / 0 |
| +250 | 26.35–26.75 | 9.5443560 | 9.485568 | 3 / 1 |
| +300 | 26.4–26.8 | 9.5443560 | 9.485568 | 3 / 1 |

Early protection can finish before the critical ACK feedback, while late protection can start after the loss decision. These discrete outcomes do not prove that every intermediate offset succeeds, nor define a universal error bound. They shift both interval endpoints and both route-event windows; they do not simulate control-message transport latency, loss, clock drift or a stochastic prediction-error distribution.

The second event also prevents an overbroad benefit claim: over the fixed 74.5–77.0 s window, baseline delivers 9.626880 Mbit/s and protected runs 9.618048 Mbit/s. The protected trajectory contains 12 retransmissions and two recovery entries there. Changed earlier behavior can change later congestion and packet phase. We therefore report the first-event benefit and whole-run effect separately, and do not claim that protection removes every recovery or improves both event windows.

## All 52 phase-two cases

`Rec` and `Loss` count transitions into `CA_RECOVERY` and `CA_LOSS`. `Bypass` is the observed upfront exemption trace. All cases below exit successfully. A dash means that the bulk transfer remains unfinished and has no completion time. Goodput and delivered-byte values for every row are retained in the linked CSV/JSON.

| Case ID | Completion s | Drops | Retx | Rec | Loss | Bypass |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| p2-f3-base-first | 1.150124001 | 1 | 1 | 0 | 1 | no |
| p2-f3-guard20-first | 1.150124001 | 1 | 1 | 0 | 1 | no |
| p2-f3-exempt21-first | 1.150124001 | 1 | 1 | 0 | 1 | yes |
| p2-f4-base-first | 0.250592160 | 1 | 1 | 1 | 0 | no |
| p2-f4-guard20-first | 1.150124001 | 1 | 1 | 0 | 1 | no |
| p2-f4-exempt21-first | 0.250592160 | 1 | 1 | 1 | 0 | yes |
| p2-f8-base-first | 0.250592160 | 1 | 1 | 1 | 0 | no |
| p2-f8-guard20-first | 1.150124001 | 1 | 1 | 0 | 1 | no |
| p2-f8-exempt21-first | 0.250592160 | 1 | 1 | 1 | 0 | yes |
| p2-f20-base-first | 0.251509920 | 1 | 1 | 1 | 0 | no |
| p2-f20-guard20-first | 1.150124001 | 1 | 1 | 0 | 1 | no |
| p2-f20-exempt21-first | 0.251509920 | 1 | 1 | 1 | 0 | yes |
| p2-f22-base-first | 0.350597120 | 1 | 1 | 1 | 0 | no |
| p2-f22-guard20-first | 0.450716800 | 1 | 1 | 1 | 0 | no |
| p2-f22-exempt21-first | 0.450716800 | 1 | 1 | 1 | 0 | no |
| p2-f80-base-first | 0.952802080 | 1 | 1 | 1 | 0 | no |
| p2-f80-guard20-first | 0.952115040 | 1 | 1 | 1 | 0 | no |
| p2-f80-exempt21-first | 0.952115040 | 1 | 1 | 1 | 0 | no |
| p2-f20-guard8-first | 0.350482400 | 1 | 1 | 1 | 0 | no |
| p2-f20-base-middle | 0.350711200 | 1 | 1 | 1 | 0 | no |
| p2-f20-guard20-middle | 1.251165120 | 1 | 1 | 0 | 1 | no |
| p2-f20-exempt21-middle | 0.350711200 | 1 | 1 | 1 | 0 | yes |
| p2-f20-base-last | 1.351284160 | 1 | 1 | 0 | 1 | no |
| p2-f20-guard20-last | 1.351284160 | 1 | 1 | 0 | 1 | no |
| p2-f20-exempt21-last | 1.351284160 | 1 | 1 | 0 | 1 | yes |
| p2-f80-base-last | 1.552210560 | 1 | 1 | 0 | 1 | no |
| p2-f80-guard20-last | 1.552210560 | 1 | 1 | 0 | 1 | no |
| p2-f80-exempt21-last | 1.552210560 | 1 | 1 | 0 | 1 | no |
| p2-f20-base-no-loss | 0.251279840 | 0 | 0 | 0 | 0 | no |
| p2-f20-guard20-no-loss | 0.251279840 | 0 | 0 | 0 | 0 | no |
| p2-f20-exempt21-no-loss | 0.251279840 | 0 | 0 | 0 | 0 | yes |
| p2-step20-base | 0.251050400 | 0 | 0 | 0 | 0 | no |
| p2-step20-guard20 | 0.251050400 | 0 | 0 | 0 | 0 | no |
| p2-step20-exempt21 | 0.251050400 | 0 | 0 | 0 | 0 | yes |
| p2-step80-base | 0.611527200 | 0 | 8 | 1 | 0 | no |
| p2-step80-guard20 | 0.430944960 | 0 | 0 | 0 | 0 | no |
| p2-step80-exempt21 | 0.430944960 | 0 | 0 | 0 | 0 | no |
| p2-leo-base | — | 499 | 523 | 41 | 1 | no |
| p2-leo-guard20 | — | 486 | 507 | 40 | 1 | no |
| p2-leo-exempt21 | — | 486 | 507 | 40 | 1 | no |
| p2-notify-early200 | — | 499 | 523 | 41 | 1 | no |
| p2-notify-early100 | — | 486 | 507 | 40 | 1 | no |
| p2-notify-late100 | — | 486 | 507 | 40 | 1 | no |
| p2-notify-late200 | — | 486 | 507 | 40 | 1 | no |
| p2-notify-late250 | — | 499 | 523 | 41 | 1 | no |
| p2-notify-late300 | — | 499 | 523 | 41 | 1 | no |
| p2-f21-base-first | 0.350482400 | 1 | 1 | 1 | 0 | no |
| p2-f21-guard20-first | 0.450716800 | 1 | 1 | 1 | 0 | no |
| p2-f21-exempt21-first | 0.350482400 | 1 | 1 | 1 | 0 | yes |
| p2-f80-base-no-loss | 0.452206240 | 0 | 0 | 0 | 0 | no |
| p2-f80-guard20-no-loss | 0.452206240 | 0 | 0 | 0 | 0 | no |
| p2-f80-exempt21-no-loss | 0.452206240 | 0 | 0 | 0 | 0 | no |

## Provenance and report claims

The [execution record](phase2_execution.json) lists all 52 commands, question families and exit codes. The original 46-case batch took 86.168 seconds and the added six-case batch 0.251 seconds on the original hardware. Their recorded sum, **86.419 seconds**, excludes time between batches and is not the duration of one continuous 52-case execution. [Results CSV](phase2_results.csv) and [results JSON](phase2_results.json) map every case to delivered bytes, completion, goodput, loss/recovery counts and patch hash. [Runner](run_phase2.py) generates first/middle/last segment-loss controls, finite delay steps, stable controls, bulk comparisons and offsets; [analyzer](analyze_phase2.py) verifies finite transfer completion before recording completion time. Patch SHA-256 is `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`.

The 52 cases comprise 31 finite actual-loss controls, six finite no-loss controls, six finite delay-step controls, three bulk LEO controls and six nonzero window offsets. Zero offset is represented by `p2-leo-exempt21`. The initial 23-case v5 volume replay remains historical evidence. A subsequent [complete v6 comparison](evidence/reproduction_v6.json), using a new volume initialized from unmodified official source, verifies all **75 declared cases**: all simulations succeed and **600 raw/legacy input files plus all 75 full analysis JSON files match byte for byte**. Simulation replay time is 377.093 seconds, excluding build, analysis, comparison and rendering. These are reproduction checks for overlapping deterministic conditions, not independent statistical samples, rendered-image equality or proof of every possible discard path.

These measurements support a refined, scoped proposal: retain baseline detection for known small transfers while applying route-informed tolerance to selected larger transfers. They also expose what it still cannot do: handle arbitrary residual-flight starvation, eliminate final-segment timeout, infer future routes without operator information, or establish performance of current Linux RACK. Prior reordering protection is acknowledged in the earlier note; cutoff and window choices remain exploratory rather than proved optimal.
