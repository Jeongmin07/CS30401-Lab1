# Renewal timing sensitivity and assignment alignment

Owner: Jeongmin07. Follow-up on our PR15, dependent on PR14 v1 at
4a91c32cf90ea4aa6f81cc81accb2136e6e1f193. Declared before execution.
This is research evidence, not a change to the team's PLAN or a merge decision.

## Assignment boundaries checked against the original handout

The original `CS30401_26F_Lab1_Handout.pdf` was read on 2026-10-11.
Page 3 permits changing stations, satellites, link rates, queues, TCP, traffic,
and simulator code, with a stated basis for each value. Pages 4-5 require a
specific TCP mechanism, justified relevance, realistic information assumptions,
matched baselines, costs and limitations. Pages 6-7 require every reported
result to regenerate from code and README alone, in a fresh course environment.
Page 9 explicitly values explanation of marginal results.

This study changes only the existing endpoint renewal-history length and,
in a separately labeled capacity check, both link rates. No new model features,
TCP source change, route oracle, outage, random loss, or dependency is added.
The official pinned ns-3.48/Hypatia image and supplied 200-second Seoul-London
state remain the platform. Synthetic competition is a diagnostic control;
the actual problem and improvement must remain demonstrated in the LEO model.

## Different approaches assessed

| Perspective | Possible improvement | Evidence and decision |
| --- | --- | --- |
| Mechanism | Renew an obsolete delay reference sooner/later | Run a small, fully reported neighborhood around PR14's 20-cycle choice; no optimum claim. |
| Other users | Evaluate aggregate delivery, CUBIC share, fairness and actual queue delay | Retain fixed-propagation CUBIC control, where renewals reveal congestion absorption. |
| Network conditions | Change available capacity while holding policy fixed | Predeclare 50 Mbps, half the original 100 Mbps, to test BDP/response sensitivity; not a measured satellite capacity claim. |
| Alternative control law | Adapt Vegas alpha/beta | Already tested in PR15; lower LEO benefit and worse sharing. Do not repeat it. |
| Fresh delay measurement | Slow down to drain self-induced queues | Requires fresh RTT/probe state; CUBIC can refill queues. Defer the larger implementation rather than equating SRTT minima with empty-queue propagation. |
| Explicit network information | Route/queue notifications | Potentially separates causes but requires realistic delivery, accuracy and cost evaluation. No such signal is implemented. |
| Submission quality | Reproduce without Git metadata | Existing runner assumes Git. This is a final-package gap even though current research runs are reproducible from a clone. |

Literature: La, Walrand and Anantharam, *Issues in TCP Vegas*, UCB/ERL M99/3
(1999), Sections 3-4, establishes the stale-reference/persistent-congestion
problem and earlier renewal ideas: https://www2.eecs.berkeley.edu/Pubs/TechRpts/1999/ERL-99-3.pdf .
The fixed version of LEDBAT++ draft -06, Sections 3.3/4.4/4.5, discusses
measurement aging and slowdowns: https://datatracker.ietf.org/doc/html/draft-irtf-iccrg-ledbat-plus-plus-06 .
Neither is claimed to implement our exact ns-3 SRTT-based rule. Vegas is a
course implementation and an interpretable delay-based mechanism, not claimed
to be the dominant modern Internet TCP; the report must justify this scope.

## Predeclared matrix and interpretation

Ten runs, two workers, no automatic retries or parameter search:

1. `s1-leo-r10/r20/r40`: supplied LEO, 100 Mbps, q100, renewal enabled.
2. `s1-fixed-comp-r10/r20/r40`: fixed 90 ms propagation RTT, 100 Mbps,
   q100, Vegas at 0 s and CUBIC at 80 s; renewal enabled.
3. `s1-rate50-base/r10/r20/r40`: supplied LEO, 50 Mbps, q100,
   ordinary Vegas or renewal. All otherwise identical to item 1.

Rounds 10/40 halve/double the existing 20-valid-CA-cycle history. These are
cycle counts, not fixed wall-clock periods. The 1 ms rise threshold is held
constant; adaptive thresholds remain OFF. All cases last 200 s, bulk size
100 GB, seed 123456789, no pacing, MSS 1380, existing buffers/startup/loss rules.
Micro initial ssthresh remains 900 MSS; LEO retains its original settings.
100 Mbps baseline and adaptive results are reused only with their original
provenance; new r20 measurements must match the original PR14 measurements.

Primary metrics: full-200s receiver app goodput in LEO; both flow goodputs,
aggregate, Jain fairness, actual forward queue wait and drops in common
[80,200) competition. State traces check actual policy and renewal events.
The 50 Mbps comparisons use their own newly measured baseline. It is one
capacity sensitivity check, not an independent path or statistical sample.

Do not select a winner on Vegas throughput alone. A candidate dominates r20
here only if LEO goodput, competition aggregate and Jain are at least r20,
and competition mean queue delay is at most r20 (with at least one strict
improvement). Otherwise report the tradeoff and preserve the main candidate.
50 Mbps results are validation conditions, not a second optimization stage.
One representative new setting is replayed in the retained independently
built second volume. All raw results and manifests are preserved.

## Status

Declared; results pending. The existing full patch is unchanged. Launch commit
and exact commands will be recorded by the matrix and per-case manifests.
