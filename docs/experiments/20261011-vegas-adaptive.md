# Declared Vegas adaptive follow-up

Owner: Jeongmin07. Status: declared before implementation/simulation.
Base: main b60e8e0; dependency: PR14 4a91c32 (selected source tools/v1 patch).
Scope: code/vegas-adaptive and this experiment's evidence/documentation.

Question: can published endpoint threshold adaptation recover course Vegas
goodput without upwardly replacing its propagation reference, and what queue
and competing-CUBIC costs follow? This is an empirical comparison, not a claim
that threshold adaptation identifies route changes or eliminates congestion.

See code/vegas-adaptive/README.md for predeclared mapping and initial cases.
The v1 recent-min renewal result is the existing comparator, not combined with
this candidate. No new simulations have run at this declaration commit.
