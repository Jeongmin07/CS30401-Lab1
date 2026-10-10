# Vegas renewal v2: preserve the existing beta budget

This is a continuation of [PR14](https://github.com/Jeongmin07/CS30401-Lab1/pull/14), not a team-approved final topic. The original v1 patch, scripts, evidence, and published raw archive remain unchanged in the parent folder.

## Question declared before simulation

Does preserving Vegas's existing beta packet estimate at each upward reference renewal retain useful adaptation to a longer path while reducing the queue cost of v1's full recent-min replacement?

Only one policy change is tested. For current segment window `w`, existing `beta=4`, and the minimum SRTT `R` of the existing 20 valid CA cycles, use `C=floor(R*(w-beta)/w)` in integer nanoseconds. Reject if `w<=beta` or the unchanged double calculation would give `diff<beta`. Renew only if `C-oldBase>=1ms`; retain history on a rejected candidate; clear it after a successful renewal and at the inherited invalid-cycle/ENABLE/DISABLE transitions. Keep the original downward minimum, startup, loss recovery, and +/-1 MSS decision. The new `RenewalPreserveBeta` switch defaults off. The beta estimate is an internal Vegas estimate, not a measurement of actual queue packets. This does not classify routing changes or cap accumulated reference inflation.

## Declared comparisons

Pinned official image digest: `sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`.
All five original scenarios are rerun for 200s, seed123456789, 100Mbps, queue100. Each has stock Vegas and budget-preserving renewal: fixed45ms one-way, 45->48ms at100s, those two cases with CUBIC starting80s, and the supplied Seoul-London LEO case. No post-result tuning or silent retries. Two workers. Compare foreground and competitor on the same80-200s window, aggregate delivery, direct queue waits, TcDrop, retransmissions/recovery, and all renewal decisions. Additionally replay v1 renewal through the new binary in fixed competition and LEO; compare original measurement CSV bytes. These are deterministic controls, not statistical repetitions.

A new Docker volume is used; the fresh image worktree was clean but needed `git update-index --refresh` before `git apply --index`. No source reset was used. Apply this folder's **complete** `ns3.patch` to a fresh course tree, then `./ns3 build`; do not also apply the parent patch. It contains the prerequisite passive instrumentation and dormant CUBIC study code, which is not enabled here.

Inside the image, repository at `/work`:

```sh
python3 /work/code/vegas-study/v2/run_matrix.py --image-digest sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4
python3 /work/code/vegas-study/v2/analyze_matrix.py --launch-commit FULL_LAUNCH_COMMIT --out /tmp/vegas-v2-analysis --workers 2
python3 /work/code/vegas-study/v2/audit_budget.py --root /tmp/cs30401-vegas-v2 --out /tmp/vegas-v2-audit
python3 /work/code/vegas-study/v2/export_evidence.py --analysis-root /tmp/vegas-v2-analysis --out /tmp/vegas-v2-export
```

Each runner refuses a dirty repository or reused case, checks driver/full staged patch, and hashes the executable, all shared libraries, code, actual settings and command. The v2 analyzer changes the reference contract to candidate<=recent and records the new fields; `audit_budget.py` independently reconstructs every history and exact candidate. Large original traces stay outside Git; evidence and publication receipts are added after validation.

## Completed result and decision

The declared ten runs and two compatibility runs completed at launch commit `ac133157c5faa3dac56534ab105cd2ed804fd12c`. **V2 is not selected to replace v1.** LEO goodput is 53.7309072Mbps (+29.44% over stock 41.5113384), but below v1 69.3432336. In step+CUBIC competition (common80-200s), mean actual forward queue wait is 5.77205ms, higher than v1 4.43401ms. Smaller reference inflation/renewal count does not guarantee lower queue costs. See [the Korean evidence/decision record](../../../docs/experiments/20261010-vegas-budget-renewal.md) and [three-way comparison](evidence/comparison/compare.csv). V1 files remain unchanged.

Independent audit: 26,223 primary state rows,61 total renewals (30 budget updates),0 errors, every accepted budget decision integer diff>=5. Compatibility 131/131 measurement CSVs match (timing/internal versioned state excluded). A fresh complete-patch build plus fixed-CUBIC/LEO budget replay matches37/37 measurement CSVs including v2 state, with input/policy/source/executable/library checks. Deterministic replay is not a statistical repetition. Original failed clone-setup attempts are retained; no simulation retry or policy fitting was hidden.

`evidence/analysis-matrix.json` merges the completed eight-micro and two-LEO analysis receipts. The legacy `first-false-renew` window labels in those original outputs refer to the **v1 reference window**, not a v2 renewal history. Future `analyze_matrix.py` names it `v1-false-reference`; only the inherited metadata description changed after both analysis jobs finished. Simulation launch and post-hoc helper identities remain separate.

For an exact three-way comparison of exported results:

```sh
python3 /work/code/vegas-study/v2/compare_results.py --v1-export /work/code/vegas-study/evidence --v2-export /tmp/vegas-v2-export --out /tmp/vegas-v2-compare
```

To compare fresh representative simulations, create the inventory from the primary cases, transfer it, and use the same helper (available after the simulation launch commit):

```sh
python3 /work/code/vegas-study/v2/compare_records.py --inventory --include-state --root /tmp/cs30401-vegas-v2 --cases v2-fixed-comp-renew v2-leo-renew --out /tmp/new-primary-inventory.json
python3 /work/code/vegas-study/v2/compare_records.py --reference /tmp/new-primary-inventory.json --root /tmp/cs30401-vegas-v2 --map v2-fixed-comp-renew=replay-v2-fixed-comp-renew --map v2-leo-renew=replay-v2-leo-renew --strict-policy-replay --out /tmp/new-replay-comparison.json
```

Original archive: [vegas-budget-20261010](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-budget-20261010),1,570,260,935bytes, SHA256`780baeaf73468f4b914f9c49abf3048a480c9275ed2b49518c826ad9ce67bf4a`. The verified 389-file inventory covers primary logs/full original analysis/audit/fresh-replay records. Do not include large logs, supplied state, ns-3 tree or build in the final course ZIP. This study does not select the team's final topic or merge PR14.
