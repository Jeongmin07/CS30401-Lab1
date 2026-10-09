# Parameter Bases and Deployment Assumptions

**Independent report material by kim-seongchan with GPT assistance.** This note explains the initial CUBIC study's settings and the assumptions required by its selective reordering protection. It excludes teammates' results and is not an agreed team design. The completed measurements and exact source evidence are in [EXPERIMENT_NOTE.md](EXPERIMENT_NOTE.md); this note adds interpretation, not new experiments. Future controllers must be reported separately from the initial prototype.

## What the implemented idea changes

The tested sender runs ns-3.48 CUBIC with SACK and PRR recovery. Its default `ReTxThreshold` is 3. The prototype temporarily raises this packet-count threshold during externally supplied intervals, then restores 3 after a permitted final socket state. It changes loss detection, including SACK presumed-loss marking, rather than CUBIC's window-growth equation. Existing scoreboard loss marks are not erased by increasing the threshold.

The sender receives a configured threshold and absolute simulator-time windows through the flow schedule's `AdditionalParameters`, for example:

```text
study_threshold=20;study_windows=26100000000:26500000000|74900000000:75300000000
```

This is **oracle scheduling**: the experimenter has inspected the known course state and supplies the times before the run. There is no implemented operator-to-sender notification protocol, measured notification latency, or automatic prediction from public satellite orbits. The sender does not currently inspect the forwarding state or path-truth table itself.

Restoration is scheduled after ACK processing and is permitted in `CA_OPEN` or `CA_LOSS`; it is deferred in other congestion states. The configured restoration deadline is an observation limit, not an unsafe force-reset. Consequently the actual protected interval can exceed its requested end. These are implementation details with measured costs, not a guarantee that a real-loss response is preserved.

## Information, recipient and prospective source

The deployment point is **sender-side TCP**. The tested change needs no receiver wire-format modification. A prospective network operator would supply advance information about affected flows or terminals, while receivers would continue normal ACK/SACK processing. Deploying the idea would require a sender implementation and an interface connecting operator information to TCP; modifying an ns-3 attribute does not establish a compatible Linux implementation.

The minimal current input is the protection interval and threshold. A prospective interface could instead announce an affected path or terminal, a route-update identifier, an expected transition time, an expiry or cancellation, and a direction-specific delay-change estimate or uncertainty bound. The sender could derive a protection window from that notice. This message format is a proposal, not a protocol evaluated here.

An operator controlling scheduled forwarding can in principle obtain the notice from its planned old/new forwarding snapshots and topology model before installing the update. It would also need to map the update to the affected sender and deliver it in time. This assumes access to the actual routing policy and a stable enough schedule. Congestion-driven rerouting, unscheduled failure and cancellations would weaken that assumption.

Public orbits alone are insufficient to identify the actual route change: geometry does not specify which links, access satellites and forwarding policy an operator will choose. Orbit-based prediction would additionally need topology, visibility constraints, routing policy and its update schedule. We have not demonstrated that those inputs are available to an ordinary Internet sender. Operator cooperation is therefore the main prospective information source, not a capability already present in TCP.

The course path-truth diagnostic reports **two-direction propagation RTT**. A decrease in that sum is a useful event selector but does not by itself prove forward-path overtaking. Receiver sequence evidence establishes the studied reordering. An operational predictor should reason about the forward-path transition and packets already in flight; the current work does not trace their live per-hop routes or derive a reliable maximum reordering depth from the RTT sum.

## Accuracy and assumptions

For the idea to prevent a packet-count loss decision, the threshold must rise before the relevant SACK/ACK processing marks the segment lost. An announcement arriving after that decision cannot repair it merely by raising the threshold. In the tested first episode, recovery occurs at 26.328788841 seconds: protection starting at 26.1 seconds works, whereas the tested late window starting at 26.4 seconds produces the baseline result. These points demonstrate sensitivity to timing; they do not establish a universal allowable error or the latest safe activation time.

A real notice must account for delivery latency, scheduling delay and clock offset between operator time and sender time. Earlier activation or a wider interval may tolerate uncertainty, but also exposes more genuine losses to the larger threshold. The minimum required accuracy is therefore conditional on the event's packet phase, loss-marking time and the sender's traffic, rather than a fixed accuracy derived from satellite speed. False positive notices and missing notices have not been systematically evaluated in the initial matrix.

The end of the interval must cover the delayed packets and their feedback, not only the forwarding update itself. Waiting for a safe state also makes actual duration workload-dependent. In one genuine-loss control the nominal end is 10.3 seconds but restoration occurs at 10.4237584 seconds. In the short-flow control the nominal end is 0.5 seconds but restoration occurs at 1.100009281 seconds. A shorter requested window alone is therefore not a proven fix for the short-flow failure.

Other assumptions are explicit: SACK is available; both compared runs use the same defined scenario; notifications relate to the sender's current path; and the model's packet-count loss detection remains the relevant mechanism. The initial controller does not distinguish genuine congestion from reordering once protection is active. It also does not establish correctness for a modern stack using RACK-TLP, for several competing flows, or for unannounced interruptions.

## Costs and boundaries supported by data

The sender pays for timer/state handling and altered loss detection. The prospective operator pays for forecasting, affected-flow mapping and notice delivery. Notice message size, bandwidth, processing overhead and deployable kernel integration have **not** been measured, so no numerical overhead claim is justified. The extensive packet tracing is research instrumentation, not a proposed production requirement or a measured control overhead.

The measured costs include delayed genuine-loss recovery, deferred restoration and changed congestion trajectories. In the stable bulk-flow control, first retransmission and validated gap repair are each delayed by 6.99792 ms under threshold 64. In the 20-segment flow, threshold 20 leaves only 19 following ACK opportunities; application completion changes from 0.251509920 to 1.150124001 seconds. The current data therefore reject a general claim that selective activation preserves the baseline response to real loss. Small-queue whole-run goodput also decreases despite improvement around the first route event.

The positive claim remains useful but narrow: the tested selective activation removes one verified unnecessary recovery and improves first-event delivery by about 1.44%, while its whole-run benefit is about 0.023% in that case. These results support investigating a more conservative activation/termination policy; they do not prove it will improve all traffic. Reordering robustness is known prior art, including [RFC 4653](https://www.rfc-editor.org/rfc/rfc4653.html), and time-based loss detection is described in [RFC 8985](https://www.rfc-editor.org/rfc/rfc8985.html). The study's contribution is its route-informed activation experiment and measured benefit/cost boundary.

## Parameter bases for the initial experiments

Values below are controlled diagnostic choices. They were selected while investigating reproduced behavior, not as a preregistered optimization study. No rate or queue capacity is claimed to measure deployed Starlink, and no tested threshold is called universally optimal.

| Setting | Initial values | Basis and interpretation |
| --- | --- | --- |
| Environment | Official `2026f-v1`, ns-3.48; pinned image and patch | Supplied course/Hypatia environment. Exact digest, source commit and manifests identify the implementation being studied. |
| Network state | Default Starlink shell 1; Seoul–London; 100-ms forwarding updates | Official example supplies motion, geometry and forwarding changes. One ground-station pair limits generality. |
| TCP and defaults | CUBIC/SACK/PRR; MSS 1,380 bytes; initial cwnd 10 segments; 32-MiB buffers | Retain the course settings instead of adding unrelated tuning. CUBIC is a relevant standard controller, but the observed loss detector lacks RACK-TLP. |
| LEO link rates | Equal ISL/GSL rates of 10 or 100 Mbit/s | A tenfold controlled rate comparison changes how many packets can be in flight during a transition. This is sensitivity analysis, not empirical capacity modeling. |
| LEO device queues | 100 packets at 10 Mbit/s; 1,000 at 100 Mbit/s; 50 at 10 Mbit/s | The first pair keeps a payload-only per-device queue-time proxy equal: `Q × 1380 × 8 / rate = 110.4 ms`. The smaller queue halves that proxy. Headers, ACKs and multiple hops prevent treating it as an exact end-to-end delay bound. |
| Reordering thresholds | Default 3; 8, 20 and 32 at 10 Mbit/s; 64 in higher-rate/micro controls | Compare default, continuously raised and selectively raised tolerance, and probe sensitivity. Larger values admit more reordering while risking delayed genuine-loss detection. Identical outcomes for 8/20/32 establish no optimum. |
| LEO protected windows | 26.1–26.5 and 74.9–75.3 seconds | Include the known 26.2/75.0-second updates, with 100 ms lead and 300 ms nominal follow-up. Pilot-informed oracle settings, not a derived universal window. |
| Late windows | 26.4–26.8 and 75.2–75.6 seconds | Preserve window length while delaying activation by 300 ms. This isolates one timing error; it is not a full jitter distribution. |
| LEO run duration | 200 seconds, or 85 seconds at 100 Mbit/s | 200 seconds uses the complete supplied example. 85 seconds includes both 26.2 and 75.0 events while reducing detailed-trace workload; only events within the actual duration are analyzed. |
| Bulk transfer | 100 GB, starting at zero | Course-style sustained load, intentionally unfinished during the observation period. This permits event-local delivery and full-run goodput comparison. |
| Microbenchmark | Two nodes; 100 Mbit/s; 2,000-packet drop-tail queues; 20 seconds | Isolate a known delay transition or one intentional loss. Large finite queues do not eliminate ordinary congestion drops; the measured drop traces must be consulted. |
| Micro initial ssthresh | 900 segments | At 100 Mbit/s and 100-ms propagation RTT, payload BDP is about `100e6 × 0.1 / (8 × 1380) = 906` segments. This controls slow-start transition near that scale; it does not set initial cwnd to 900. |
| Micro delay step | One-way 50 to 45 ms at 10 seconds; stable control stays at 50 ms | A simple 10-ms RTT decrease near the LEO change's scale. It is a mechanism control, not a replacement for the multi-hop LEO scenario. |
| Micro protection | Threshold 64; 9.99–10.3 seconds | Start 10 ms before the controlled event and include feedback afterward. These oracle choices test protection and its loss cost under the same timing. |
| Intentional bulk loss | First data packet arriving at/after 10.06 seconds | Place one observed physical receive drop within protection on an otherwise stable propagation path. This diagnostic is not a weather-loss frequency model. |
| Short-flow loss control | 27,600 bytes; stable one-way 50 ms; one first-data-segment drop at/after 0.15 seconds; four-second run | `27600 = 20 × 1380`: deliberately expose threshold 20 when the finite flow supplies only 19 following segments. Four seconds includes the observed timeout and complete delivery. The dropped packet is not the last segment. |
| Short-flow protection | Threshold 20; requested 0–0.5-second interval | Deliberately overlap the actual loss to quantify a false-activation failure. This is an adverse control, not a predicted route event. |
| Routing timing control | Hold the 26.1-second forwarding snapshot at 26.2–26.8; resume current state at 26.9 | Test dependence on the actual update timing while satellite motion and geometry continue. It is not static-distance routing or a deployable policy. |
| Randomness | LEO configuration seed 123456789; deterministic supplied state and micro controls | Replays verify reproducibility, not independent statistical samples. No stochastic radio-loss model is added. Additional controlled seeds would be needed if a stochastic loss/notification model is introduced. |

The environment removes root queue discs and uses device drop-tail queues. The final microbenchmark does the same explicitly and checks absence, avoiding an automatic AQM confound. Queue, traffic-control, IP and device drop traces support loss classification. Their coverage still does not prove every possible receiver TCP rejection path is audited.

## Suggested paper structure and identity

The repository README identifies **Team 5**. Its context documents do not supply all three members' complete submission names; GitHub handles are not substitutes for verified names. The report's author line must be completed with the actual names rather than inferred from logins. This independent note does not establish the team's agreed final scope.

The handout permits one or more problems and ideas. A coherent six-page body can organize this work as one validated loss-detection question with timing, queue and finite-flow subquestions. A separate BBR or Vegas problem needs its own causal evidence and evaluated idea; their initial throughput probes do not yet satisfy that requirement.

| Required section | Suggested content and approximate space |
| --- | --- |
| Introduction | The precise research question, relevance of CUBIC, and limited contribution; about half a page. |
| Problem Statement | Original acceptance, SACK trigger, late covering ACK, routing control and consequence; about one page. |
| Proposed Idea(s) | Sender threshold change, information source, accuracy assumptions, safe-state restoration and prior art; about one page. |
| Experiment Setup | Parameter bases, manifests, drop coverage, controls and metric definitions; about one page. |
| Evaluation | Event and whole-run benefit, sensitivity, genuine-loss/FCT costs and limitations; about two pages. |
| Conclusion | What is established, what fails and remaining scope; about half a page. |

These allocations are editorial suggestions, not required section lengths. Use the unchanged English IEEE conference two-column, 10-point Times template. Sections 1–6 together must fit within six pages; references and optional appendix are excluded from that limit. Keep essential evidence in the main body and move the complete configuration table or extra sensitivity detail to the appendix if needed. Every reported result still needs a reproducible command.

Sources: the supplied Lab 1 Handout, STEP 1–3 and Submissions; the Lab Environment Guide; and the initial study's committed manifests and source patch. CUBIC's standard relevance is documented by L. Xu, S. Ha, I. Rhee, V. Goel and L. Eggert, [RFC 9438, 2023](https://www.rfc-editor.org/rfc/rfc9438.html). S. Bhandarkar, A. L. N. Reddy, M. Allman and E. Blanton, RFC 4653, 2006; Y. Cheng, N. Cardwell, N. Dukkipati and P. Jha, RFC 8985, 2021. The environment foundation is S. Kassing, D. Bhattacherjee, A. B. Aguas, J. E. Saethre and A. Singla, [“Exploring the ‘Internet from space’ with Hypatia,” ACM IMC, 2020](https://bdebopam.github.io/papers/imc2020-hypatia.pdf).
