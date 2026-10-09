# CS30401 Lab1 Research Proposal

**Reading order:** [EXPERIMENT_NOTE.md](EXPERIMENT_NOTE.md) is the authoritative completed first-round result. This file preserves the candidate questions, original pilot limitations and subsequent investigation history; statements about a pilot's next gate are historical, not the current completion status.

**Author:** kim-seongchan with GPT assistance. **Updated:** October 10, 2026, KST. This is a proposal for discussion, not an agreed team plan. It excludes teammates' existing results. Compare several candidate problems, then develop reproducible investigations connecting specific TCP mechanisms to improvements, benefits, and costs.

## Research question and decision gate

The provisional question is: **Can raising TCP's reordering tolerance only around LEO path-shortening events reduce unnecessary recovery while preserving the response to genuine congestion better than raising the threshold continuously?**

A shorter new path can let later packets overtake packets already travelling along the old path. Duplicate ACKs and SACK feedback may then trigger loss recovery even when the delayed packets were not dropped. This is a candidate mechanism, not a conclusion from the completed pilot. CUBIC supplies the congestion-control baseline; the proposed change concerns its TCP loss detection, not a new CUBIC growth equation.

Continue only after demonstrating receiver-side reordering, corresponding ACK feedback, and harmful recovery unexplained by actual drops in a relevant modern TCP. Correlation with a smaller congestion window is insufficient. Otherwise reject this candidate and investigate alternatives, such as BBR's adaptation to changing propagation RTT. NewReno can clarify mechanisms but cannot alone establish a modern-TCP problem.

The handout explicitly permits **one or more problems and one or more ideas** (STEP 1 and STEP 2); it does not require a single research question. A common question with several diagnostic subquestions can support a coherent report. Multiple unrelated projects need separate causal evidence, implementations, and evaluations, all within the same six-page body and reproducible package. Scope is therefore a practical decision, not a grading rule invented by the team.

| Candidate | Evidence needed to continue | Small idea and decisive control |
| --- | --- | --- |
| Route-shortening and reordering | Receiver sequence inversion, matching ACK/SACK feedback and avoidable recovery without a matching actual drop | Temporary tolerance; compare default, always-high and event-window settings, including true loss |
| BBR propagation RTT model staleness | A verified stored RTT estimate that fails to track a changing propagation baseline and causes a quantified consequence | A bounded refresh rule; separate geometric RTT change from queues and measure refresh cost |
| Vegas delay misclassification | The implementation's base RTT and queue estimate show propagation change interpreted as congestion | A justified reference update; verify that true queueing still produces the correct response |
| Queue and BDP sensitivity | A TCP mechanism, rather than generic bufferbloat alone, explains the response to changing path BDP | A small justified rule; compare matched static and dynamic conditions, plus latency and fairness costs |

These remain hypotheses. Run limited mechanism probes before committing to implementation; do not select a candidate solely by throughput ranking. The instrumented reordering probe comes first because its independent baseline has already run.

## Verified environment and present status

Independent work uses the official `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1` image in container `cs30401-kim-study`, with a separate ns-3 volume. The image digest is `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`; the environment source commit is `f77e9a6a850805741d7290913c88ffe43dcae4ca`.

The official check completed: 9,992 pings; ping RTT minus geometric truth had median 0.672 ms, p99 and maximum 0.805 ms, and minimum -2.580 ms. Changing paths might explain the negative tail, but this requires validation.

Two new single-flow CUBIC pilots, Seoul to London for 200 seconds, completed independently:

| Link rate | Queue per link | Final sender-acknowledged bytes | ACK-progress rate over 200 s |
| --- | --- | --- | --- |
| 10 Mbit/s | 100 packets | 238,548,180 | 9.541927 Mbit/s |
| 100 Mbit/s | 1,000 packets | 2,396,383,800 | 95.855352 Mbit/s |

These rates are not receiver-measured goodput or evidence of an improvement. Both use the same supplied path state, which contains seven changes, including propagation RTT drops of 6.634 ms at 26.2 s and 3.343 ms at 75.0 s. A cwnd reduction exceeding 15% in a single trace step occurred only at 2.172767 s in the 10 Mbit/s run and never in the 100 Mbit/s run. Default PRR recovery can change cwnd through several small steps, so this filter cannot establish absence of recovery. Neither pilot has established the proposed causal problem; packet and recovery-state instrumentation is the next decision gate.

Read-only source inspection confirms packet-count duplicate-ACK/SACK loss detection, the default `ReTxThreshold` of 3, and `TcpPrrRecovery` for recovery sending. This ns-3.48 implementation lacks RACK-TLP. Results must therefore be scoped to the tested CUBIC/SACK/PRR stack rather than generalised directly to current Linux TCP. The minimum RTO is 1 second; this does not prevent duplicate-ACK-triggered recovery. Receiver gaps trigger immediate ACKs.

The default model has moving satellites, distance-dependent propagation, instantaneous forwarding and access-satellite changes, and drop-tail queues. It has no handover outage, changing link capacity, or random wireless loss. Those behaviours must not be asserted as explanations for this experiment. The 10 Mbit/s pilot rate is an exploratory setting, not a claim about deployed Starlink capacity.

## Instrumented LEO observations

The independent version 3 trace runs now establish a specific reordering and recovery case in the tested CUBIC/SACK/PRR stack. Their coverage contains 42,782 connected hooks, including `TcDrop` at all 1,586 nodes. Source inspection separately confirms that the course LEO setup removes root queue discs. This matters because `TcDrop` alone does not observe losses inside an installed queue disc. These observations do not generalise to unverified microbenchmark setups or current Linux TCP.

At the 26.2-second path change, the baseline records five out-of-order payload arrivals. Original transmission 21,859, starting at sequence 29,734,861, reaches the receiver and is accepted with same-time application delivery at 26.283909347 seconds. The sender subsequently retransmits that already-delivered range and enters recovery at 26.328788841 seconds. No actual drop is recorded for the range. This links a sequence gap, ACK/SACK feedback, successful original delivery, and unnecessary subsequent recovery; the causal interpretation is stronger than a cwnd-only association.

Temporarily setting the tolerance to 20 during 26.1–26.5 and 74.9–75.3 seconds preserves the same original delivery at the first event while avoiding its three retransmission rows and recovery entry. The following comparison uses unique receiver application delivery, with an event window fixed to 25.7–28.2 seconds.

| Metric | Default threshold 3 | Temporary threshold 20 |
| --- | --- | --- |
| Application bytes delivered over 200 seconds | 238,608,900 | 238,662,720 |
| Whole-run application goodput, Mbit/s | 9.544356 | 9.5465088 |
| First-event application goodput, Mbit/s | 9.485568 | 9.622464 |
| Whole-run retransmission rows | 523 | 507 |
| Whole-run recovery entries | 41 | 40 |
| Actual `TcDrop` rows | 499 | 486 |

The first-event gain is about 1.44%, but the whole-run gain is only about 0.023%. Both are deterministic observations, not statistical population estimates. At 75 seconds, one reordered packet does not produce unnecessary recovery in either variant. Later genuine losses occur at different times as the changed controller alters the closed-loop trajectory; event-local loss differences must not be called a general loss-prevention property. Subsequent comparisons below test continuous thresholds, timing error, queue sensitivity and genuine loss. Generality to other ground-station paths and less accurate deployment information remains open.

The first point-to-point microbenchmarks automatically acquired a root FqCoDel queue disc through IPv4 assignment. Their application delivery remains usable, but claims excluding network drops are incomplete. Corrected runs must remove that queue disc and verify its absence on every non-loopback device. Never combine their earlier no-drop inference with the audited course LEO evidence.

### Comparison matrix and limitations

Twenty independent version 4 cases completed, with drop hooks and root queue-disc absence checked. They include default, continuous and event-limited thresholds; thresholds 8, 20 and 32; late notices; 100 Mbit/s links; smaller queues; Vegas and BBR; stable and changing point-to-point delay; and genuine packet loss. Analyze 85-second runs only against path changes inside their duration; the full 200-second state still supplies the correct earlier event deltas.

At 10 Mbit/s with 100-packet queues, continuous threshold 20 delivers 9.5469504 Mbit/s, only about 0.027% above default. Event thresholds 8, 20 and 32 produce identical 9.5465088 Mbit/s results in this tested scenario. Late activation beginning at 26.4 seconds arrives after the 26.328788841-second recovery and reproduces the baseline's result exactly. These facts support a limited timing requirement, not a universal optimal threshold.

At 100 Mbit/s with 1,000-packet queues over 85 seconds, default goodput is 95.416382118 Mbit/s; continuous or event-limited threshold 64 gives 95.422486588 Mbit/s, an improvement of about 0.0064%. Both remove the observed original-segment retransmissions around the two shortening events. With 50-packet queues at 10 Mbit/s, event-limited threshold 20 improves the first-event interval from 8.884992 to 9.560640 Mbit/s but reduces whole-run goodput from 9.1782696 to 9.144708 Mbit/s, about 0.366%. This negative result prevents a blanket throughput-improvement claim.

The corrected point-to-point step experiment also contains genuine device-queue losses: preventing its reordering recovery can change later bursts and cause new congestion. Its protected 9.5–12-second interval delivers less data than default, even though whole-run goodput increases slightly. Removing one unnecessary recovery is therefore not sufficient to show that a controller is beneficial.

For a matched packet intentionally dropped at 10.060109600 seconds on a stable path, default first retransmission occurs after 50.34912 ms. Continuous and event-limited threshold 64 delay it to 57.34704 ms. Validated receiver gap repair shifts from 306.64656 to 313.64448 ms after the drop, a 6.99792-ms penalty. All three have identical 20-second average goodput, so that aggregate hides the cost. The protected interval lasts 9.99–10.4237584 seconds, beyond its requested 10.3-second end because restoration is deferred while unsafe.

A separate short-flow version 5 control strengthens this failure case. Both variants deliver all 27,600 bytes after exactly one real packet drop on a stable path. Default completes application delivery at 0.251509920 seconds; event threshold 20 completes at 1.150124001 seconds, about 4.57 times later. It receives only 19 repeated ACKs, enters `CA_LOSS` under the timeout path, and defers restoration until 1.100009281 seconds. Their identical four-second average goodput of 0.0552 Mbit/s hides this substantial completion-time penalty. Loss detection and guard termination need explicit short-flow handling before broader deployment claims.

Vegas and BBR baseline comparisons are probes, not completed alternative research projects. Their throughput alone does not establish an RTT-model defect or a proposed fix. Continue those candidates only after tracing the implementation's internal model, separating propagation from actual queueing, and testing an appropriate control.

## How literature informs the study

[Hypatia, IMC 2020](https://bdebopam.github.io/papers/imc2020-hypatia.pdf), establishes the simulation foundation. [A Stability-first Approach to Running TCP over Starlink, 2024](https://arxiv.org/html/2408.07460v1), motivates studying route stability and packet overtaking. Its transport evaluation uses an abstract TCP model, so its conclusions need checking with the course's packet-level implementation.

[OrbCC, arXiv version 2, March 2026](https://arxiv.org/html/2508.19067v2), studies transport with network-provided congestion information using OMNeT++/INET simulations and microbenchmarks. We will borrow its practice of isolating mechanisms and measuring costs, not attempt to recreate its complete protocol in a different simulator before the deadline.

[RFC 4653](https://www.rfc-editor.org/rfc/rfc4653.html) already describes improving tolerance to reordering through delayed loss recovery. [RFC 8985](https://www.rfc-editor.org/rfc/rfc8985.html) describes time-based RACK-TLP loss detection. Protection against reordering is therefore not our invention. The possible contribution is a limited, orbit-informed activation rule and an evaluation of when its information requirements and delayed congestion response are worthwhile. Report references must contain verified authors, title, venue or publication status, and year.

## Establishing the mechanism

Align path identity and propagation-delay changes with receiver sequence numbers, cumulative ACKs, SACK blocks, retransmissions, congestion state, cwnd, and smoothed RTT. Instrument all relevant queue, device, and IP drops; observing only the ground sender's queue cannot exclude loss elsewhere. Track packet identity and timing so an original packet arriving late can be distinguished from successful delivery of its retransmission.

Include traffic-control drops and either verify that no root queue disc is installed or observe its drop hooks. Receiver wire traces run before TCP processing; acceptance requires subsequent expected-sequence advancement or matching-time application delivery. Receiver window and PAWS/input rejection remain separate loss paths. The analysis uses a custom tag for each transmission because packet UIDs are not unique transmission identities in this workload.

Measure unique application bytes delivered at the receiver as goodput. Sender ACK progress is useful for diagnosis but does not replace receiver delivery. Define event windows, warm-up handling, bins, and recovery time before comparing variants. TCP logs are event-driven; compute rates from byte differences and elapsed time rather than averaging rows.

Use a controlled path-change microbenchmark to check the mechanism and a course LEO scenario to establish relevance. Include stable-path or non-shortening comparisons. A frozen routing table still has moving satellites and changing distances, so it cannot automatically be treated as a constant terrestrial path.

## Minimal improvement and comparisons

The first implementation candidate temporarily increases `ReTxThreshold` around predicted path-shortening windows, then restores the default. Source inspection indicates that its setter also changes the transmit buffer's duplicate-ACK threshold, but raising it does not clear already marked losses. Activation must precede the relevant ACK feedback. Returning the threshold must respect outstanding ACK/SACK state; restoration should occur when the protected episode is resolved and the congestion state safely returns to `CA_OPEN`, with bounded fallback handling. Avoid changing thresholds blindly during active recovery.

Compare three otherwise identical variants: unmodified CUBIC, CUBIC with an always-high threshold, and CUBIC with window-limited protection. The always-high variant tests whether scheduling adds value beyond a general parameter increase. Keep traces and scenario inputs equivalent across variants.

An oracle schedule computed from simulation state is acceptable as an explicitly labelled upper bound. A deployment would require sender access to operator notifications or a usable orbital and routing prediction. Test early, late, missed, and inaccurate notices. Explain who provides this information, how precise it must be, and what remains unknown about real operator routing.

## Evaluation and adverse conditions

Prioritise goodput, event-local recovery time, unnecessary retransmissions, actual loss recovery delay, and RTT or queueing cost. Report both event-local and whole-run results: a short improvement can disappear in an average, while an attractive average can hide serious stalls.

Deliberately include actual queue overflow, including loss overlapping a protected window, and measure whether protection delays needed recovery or increases RTOs. Vary queue capacity with a stated BDP-related basis, examine another route or time window, and test notification error. If shared-flow tests are feasible, add fairness and aggregate throughput. These are scope checks, not permission to expand into an exhaustive sweep.

The supplied scenario is deterministic. Repeating identical inputs does not create independent statistical samples. If randomness is introduced, report several seeds and variability. Select no condition solely because it produces the largest improvement; record negative cases and parameter-selection reasons.

## Proposed coordination and execution gates

Three students each working with GPT should share agreed research questions and common artifacts. One owns problem reproduction and literature; one owns implementation and its checks; one owns independent evaluation, reproduction, and report integration. These roles require team agreement. Each handoff includes the code commit, patch, state-generation command, configuration, metric definitions, experiment identifier, and status. Record observations, hypotheses, and verified conclusions separately.

Proceed continuously through evidence gates rather than waiting for calendar milestones.

| Stage | Gate before proceeding |
| --- | --- |
| Candidate probes | A concrete mechanism and measurable application consequence occur in the tested stack; reject unsupported candidates. |
| Minimal improvement | Source behaviour and instrumentation establish that the change targets that mechanism; compare equivalent baselines. |
| Scope and adverse conditions | Real loss, prediction errors and other paths establish benefits, failures and costs. |
| Reproduction | The complete result is regenerated in a fresh course-image volume using the submission files alone. |
| Reporting and submission | Every claim maps to a trace, table or figure; formatting and contribution surveys are complete. |

The official submission deadline remains October 13, 2026, at 23:59 KST; it is not a reason to delay a completed stage.

## Report and reproducible submission

The handout specifies six grading dimensions without numeric weights: problem, idea, experimental soundness, reproducibility, clarity, and presentation. A modest improvement with a convincing mechanism and honest limits is stronger than an unsupported large claim.

Write the report in English using the unchanged IEEE conference template: two columns, 10-point Times, Team ID and all names below the title. Sections 1–6 are Introduction, Problem Statement, Proposed Ideas, Experiment Setup, Evaluation, and Conclusion, together at most six pages. References and optional appendices are excluded.

Prepare three main figure types: a causal event timeline; baseline versus improvement; and sensitivity or failure conditions. Add a setup table with parameter bases. Every axis needs a label and unit readable in print.

Submit `Lab1_{TeamID}.zip` containing `report.pdf`, `README.md`, and `code/`. Include exact commands, approximate runtimes, a figure-to-command mapping, generation scripts, analysis scripts, and an ns-3 patch produced by `make_patch.sh`. External Python dependencies require `uv`, `pyproject.toml`, and `uv.lock`. Exclude state files, simulation logs, the ns-3 source tree, and build artifacts from the submission ZIP. Reproduce from a fresh course-image volume using only the package: unreproducible figures are unsupported evidence. Every member completes the contribution survey; the October 15 presentation is at most ten minutes with everyone speaking.

## Commands and pilot artifacts

The following commands ran inside the isolated container. State generation was not changed. Each simulation automatically builds through the official wrapper; the ns-3 checkout remained unmodified during these pilots.

```bash
bash /home/ubuntu/lab/scripts/check_env.sh
bash /home/ubuntu/lab/scripts/make_run.sh /tmp/kim-pilot-cubic-10m-q100-200s /home/ubuntu/lab/data/seoul_london/state TcpCubic 10 100 200 1584 1585
bash /home/ubuntu/lab/scripts/run_sim.sh /tmp/kim-pilot-cubic-10m-q100-200s
bash /home/ubuntu/lab/scripts/make_run.sh /tmp/kim-pilot-cubic-100m-q1000-200s /home/ubuntu/lab/data/seoul_london/state TcpCubic 100 1000 200 1584 1585
bash /home/ubuntu/lab/scripts/run_sim.sh /tmp/kim-pilot-cubic-100m-q1000-200s
```

Simulation-stage wall times were approximately 12.5 seconds and 200.5 seconds, respectively, on the present Docker host. Raw outputs, configurations, and `pilot_inspection.json` are retained locally under `research/runs/`; they are excluded from the submission and are not teammate results. `research/inspect_pilot.py` is a standard-library-only preliminary inspection script. Its output explicitly records the limitations above; final evaluation will replace it with instrumented receiver and recovery metrics.
