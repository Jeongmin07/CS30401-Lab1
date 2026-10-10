# Screening alternative LEO TCP research topics

**Status: source review and bounded screening in progress, 2026-10-10.** kim-seongchan with AI assistance. Branch starts from `main` at `b60e8e019053c7d33b853510ec06c3d94ee78faf`. The user requested a different research topic after the K8/K20 competition results did not support selecting that policy as an improvement. Existing PR10/11/12 evidence and branches are preserved; this does not change the team's common plan.

The aim is to find a specific, materially degrading TCP mechanism in the course model, then assess whether a small justified change can improve it with acceptable costs. A paper-inspired candidate is not a validated solution. Reject a candidate if its mechanism is absent from the model, its measured headroom is negligible, or it needs an unjustified oracle/model extension to work.

## Candidate families and screening gates

1. **Delay-based TCP's propagation/congestion confusion (Vegas).** Existing uploaded 100-Mbit/s summaries report approximately 41.5 Mbit/s, leaving potential headroom. Their summaries do not establish the cause. Inspect the actual ns-3.48 base-RTT estimator and window decisions, then run a fresh matched baseline if warranted. Route-independent start-up/conservatism is an alternative explanation that must be checked.
2. **Model-based estimator lag (BBR).** Inspect the actual ns-3 implementation/version and minimum-RTT/bandwidth aging. Default-model capacity is constant; radio outage and fading are absent. Do not import Linux BBRv3 findings as results of ns-3's implementation. Its already high uploaded delivery rate may leave little room for a throughput improvement.
3. **Queue delay/pacing or route-stability tradeoffs.** Look for an existing, substantial queue-delay cost or a harmful routing transient. Identify deployment location and compare throughput together with delay/drops. A larger queue or an aggressive sender alone does not establish an improvement; route validity and information costs matter.

First review primary papers and local course source. Any pilot has a unique run ID and records the exact image, patch/binary/settings/source identities; raw runs remain outside Git. Use the existing canonical instrumentation only with empty guard parameters for an ordinary TCP baseline. No new threshold-guard tuning is planned here. No claim of a new successful topic is made before mechanism and matched-control evidence.

## Current sharing context

Three teammates work in separate AI chats on separate laptops. This screening is this teammate's proposal, not a task assignment or final topic selection for the others. At the starting check PR10, PR11 and PR12 were open, with no open Issues. PR10's single-flow work and PR12's threshold/coexistence work are different prior investigations; they are not edited by this branch. Final candidate ranking, primary-source links, actual pilot results and the next discriminating experiment will be added after screening.
