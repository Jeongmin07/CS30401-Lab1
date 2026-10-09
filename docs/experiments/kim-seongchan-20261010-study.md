# Independent CUBIC reordering study — 2026-10-10

Owner: kim-seongchan with GPT assistance. This is an independent exploration for team review, not an agreed team plan. Existing teammate results are excluded from the experiments and analysis.

The [experiment note](../../code/kim-study/EXPERIMENT_NOTE.md) records 23 distinct configurations and the packet-level cause, measured benefits, genuine-loss cost and negative cases. The [bundle README](../../code/kim-study/README.md) gives commands, patch versions, image digest, metrics and figure mapping. The [result table](../../code/kim-study/evidence/results.csv) and [source-row excerpt](../../code/kim-study/evidence/event26_evidence.csv) provide reviewable evidence without publishing raw traces or generated constellation state.

At the 26.2-second Seoul–London route transition, receiver-accepted original data is retransmitted when three newer SACKed segments trigger presumed loss. The covering ACK reaches the sender 1.147197 ms after recovery begins. Event-limited protection removes that episode, with about +1.44% receiver goodput in the declared event window but only +0.023% over the full 200 seconds. Continuous protection is slightly better in whole-run goodput at this operating point; selective activation has not demonstrated universal superiority.

Counterexamples are part of the result: late activation gives no benefit, a 50-packet queue loses about 0.366% whole-run goodput, and a genuine-loss 27,600-byte transfer completes in 1.150124 s rather than 0.251510 s. The detailed note states the tested ns-3.48 CUBIC/SACK/PRR scope and its lack of RACK-TLP. Neither Vegas nor BBR probe throughput establishes a causally verified alternative mechanism yet.

The handout permits one or more problems and ideas. A common question with related subquestions is a report-scope recommendation, not a required single-question format. All final claims still need to fit the six-page English IEEE report and trace to reproducible measurements. Multiple-flow fairness, other ground-station paths and realistic notification availability/error remain open.

Raw traces remain local in container `cs30401-kim-study`, `/tmp/cs30401-study/<case>/logs_ns3`; the bundle includes hashes and exact rerun commands. No PR is created: the user requested direct pushes to `main`. Common team files and other students' branches are unchanged.

Reproduction is now complete for all 23 configurations in a separately initialized official-image volume using canonical patch v5: 184 raw/legacy trace files and 23 full analysis JSON files match byte for byte. All five figures were regenerated with the locked Python environment. See the [verification record](../../code/kim-study/evidence/reproduction_v5.json) for checked files and precise source-history limits.
