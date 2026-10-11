# Verification review, 2026-10-12

Scope: ten new renewal-history/capacity runs, their analyses and figure,
historical compatibility, a standalone source ZIP, and one new fresh-volume
representative replay. This is an internal fresh review, not teammate approval.

## Requirements and scientific claims

- Read the original handout: pages 3-5 authorize justified TCP/link-rate changes
  and require a LEO problem, mechanism, matched baseline, costs and limits.
- Changed only renewal history 10/20/40, and the separately declared capacity
  condition 50 vs 100 Mbps. Same full patch, adaptation disabled, no new model.
- All ten declared cases completed and are published; none omitted for losing.
- Solo rates use 200 seconds; competition rates/Jain use common [80,200).
- Both r20 controls match 37 original PR14 measurement CSVs exactly. Reused
  100 Mbps baseline retains prior provenance; 50 Mbps baseline is freshly run.
- Independent history reconstruction validates 21,840 rows and 101 renewals.
- Neither new setting dominates r20. Preferred r40 is a balanced judgment:
  small throughput cost, lower queue wait and more equal sharing, more drops.
- R40 still renews on a fixed path. No successful route/queue discrimination,
  universal optimum, statistical significance or LEO queue measurement claim.

## Reproduction and artifact checks

- Unzipped source package has no `.git`, logs, state, ns-3 tree or build.
- New official Docker volume accepts the complete unchanged patch and builds.
- Package validates all code hashes; altered hash fails before simulation.
- R40 competition replay matches 26 measurement CSVs and every analyzed window,
  simulator sources, binary/libraries, policy/network/image/patch, and state audit.
- Runner/commit changes add package validation and are recorded explicitly.
- Only one representative package replay was executed, not all ten cases.
- Figure inspected visually: labels, units, baselines and all three settings
  are legible. Jain 1.000 in the figure is rounding of 0.999528, not exact unity.
- Primary archive: 277 files streamed and verified; replay archive: 32 files.
  Final server size/digest checks are in `publication-verification.json`.

## Issues resolved in this follow-up

1. The research runner required a host Git checkout. Added optional complete
   source-inventory verification and tested the extracted package independently.
2. An initial throughput-only interpretation would hide competition costs.
   Applied the declared multi-metric comparison and retained all tradeoffs.

Residual limits: one LEO path, two capacities, one fixed competing-flow control;
the original pure-delay-step causality control belongs to r20, not a newly run
r40 step case. The package's README explicitly identifies the historical
100 Mbps baseline line and explains its reproduction; a final report package
should run that baseline along with every selected figure/table. The full
matrix/figure workflow still needs an end-to-end final-ZIP check. Author names,
team scope, IEEE report and final submission assembly remain separate.

Verdict: PASS for the stated research and representative replay scope, subject
to successful final publication receipts. No merge or teammate approval implied.
