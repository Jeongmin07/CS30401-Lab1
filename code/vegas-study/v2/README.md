# Vegas renewal v2: preserve the existing beta budget

This is a continuation of [PR14](https://github.com/Jeongmin07/CS30401-Lab1/pull/14), not a team-approved final topic. The original v1 patch, scripts, evidence, and published raw archive remain unchanged in the parent folder.

## Question declared before simulation

Does preserving Vegas's existing beta packet estimate at each upward reference renewal retain useful adaptation to a longer path while reducing the queue cost of v1's full recent-min replacement?

Only one policy change is tested. For current segment window `w`, existing `beta=4`, and the minimum SRTT `R` of the existing 20 valid CA cycles, use `C=floor(R*(w-beta)/w)` in integer nanoseconds. Reject if `w<=beta` or the unchanged double calculation would give `diff<beta`. Renew only if `C-oldBase>=1ms`; clear history only after a successful renewal. Keep the original downward minimum, startup, loss recovery, and +/-1 MSS decision. The new `RenewalPreserveBeta` switch defaults off. The beta estimate is an internal Vegas estimate, not a measurement of actual queue packets. This does not classify routing changes or cap accumulated reference inflation.

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
