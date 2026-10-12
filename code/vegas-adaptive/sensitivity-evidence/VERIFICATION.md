# Verification review, 2026-10-12

Scope: ten new renewal-history/capacity runs, their analyses and figure,
historical compatibility, a standalone source ZIP, and one new fresh-volume
representative replay, followed by its complete ten-case workflow and historical
100 Mbps baseline. This is an internal fresh review, not teammate approval.

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
- Subsequent full package replay matches 155 matrix CSVs and all 11 original
  baseline CSVs, every analysis window, the results table and the figure PNG.
  The full matrix takes 1,044.65 seconds including analysis. Its audit again
  checks 21,840 state rows and 101 renewals. No statistical replication claim.
- Figure inspected visually: labels, units, baselines and all three settings
  are legible. Jain 1.000 in the figure is rounding of 0.999528, not exact unity.
- Primary archive: 277 files streamed and verified; replay archive: 32 files.
  Final server size/digest checks are in `publication-verification.json`.

## Issues resolved in this follow-up

1. The research runner required a host Git checkout. Added optional complete
   source-inventory verification and tested the extracted package independently.
2. An initial throughput-only interpretation would hide competition costs.
   Applied the declared multi-metric comparison and retained all tradeoffs.
3. The large PowerShell upload timed out and left a stale response. Rejected
   that response, completed a curl upload, and checked all three assets using
   fresh GitHub API size/digest data before publishing the release.
4. The initial package check covered only one case and reused a historical
   baseline line. Executed the entire README matrix/audit/plot workflow and
   the baseline from the unchanged ZIP; exact comparisons now pass.

Residual limits: one LEO path, two capacities, one fixed competing-flow control;
the original pure-delay-step causality control belongs to r20, not a newly run
r40 step case. The package's README explicitly identifies the historical
100 Mbps baseline line and explains its reproduction, now executed and checked.
The full research ZIP workflow passes. The final submission still needs its
own clean check for every selected figure/table, including any additional
PR14 or adaptive-study results. Author names, team scope, IEEE report and
final submission assembly remain separate.

Verdict: PASS for the stated research, complete package replay and verified
publication scope. Four issues resolved across this follow-up; no remaining
verification failure. No merge or teammate approval implied.
