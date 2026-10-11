# Vegas-A-inspired follow-up (Jeongmin07)

**Follow-up completed 2026-10-12:** the [renewal sensitivity study](../../docs/experiments/20261011-vegas-renewal-sensitivity.md)
adds ten declared timing/capacity cases. Forty cycles sacrifices 1.28% of the
20-cycle LEO goodput while reducing fixed-competition queue wait by 31.25% and
improving sharing; aggregate throughput falls slightly and drops increase.
This is now my preferred balanced candidate within the renewal design, not
an across-the-board winner. All original adaptive evidence below is preserved.

`run_sensitivity.py` launches the matrix; `verify_sensitivity.py` validates and
exports it; `plot_sensitivity.py` draws the comparison. Results and receipts are
in `sensitivity-evidence/`. `export_portable.py --out NEW_DIRECTORY` creates a
small Git-free replay ZIP from a clean checkout, containing a source inventory
and standalone README commands. One fresh-volume representative replay matched
26 measurement CSVs exactly. The complete ten-case ZIP replay is not claimed.
The [evidence release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-sensitivity-20261011)
provides the original raw runs and the tested source package.

This is a new endpoint-only candidate study, not a team direction or a merge decision.
Branch starts from main b60e8e019053c7d33b853510ec06c3d94ee78faf.
It reuses selected tools and the full v1 patch from PR #14 at
4a91c32cf90ea4aa6f81cc81accb2136e6e1f193, copied into this separate directory.
The upstream patch SHA256 is
25ac4286f68373ee4e33d43f5f00e8676a65fc9c8747d65f643cd0fc28202f59.
This is an explicit experimental dependency on an unmerged PR; it does not
modify the teammate's branch, canonical kim-study patch, or shared PLAN.

Candidate: adaptive Alpha/Beta and one previous valid CA-cycle throughput
estimate, based on Srijith/Jacob/Ananda (2005) section 3 and author Code3:
https://srijith.net/publications/journals/TCP_Vegas-A_COMCOM05.pdf
https://github.com/skn/vegas-a/blob/a379c93fe70d5d7b16e620d0e046a69e26a1ee0e/codes/tcp-vegas.cc.code3

Declared adaptation: course SRTT input, existing integer Vegas diff, initial
Alpha/Beta 2/4 with lower bounds 2/4, cycle-granularity cwnd +/-1 MSS. The NS-2
original uses initial/lower 1/3, different RTT/flight estimates and ACK-applied
increase. Therefore this is inspired by Vegas-A, not an exact reproduction.
Do not combine it with recent-min renewal. Startup, recovery and socket loss
handling remain the supplied implementations. Reset previous-rate validity on
Vegas disable/enable or an invalid CA cycle; the first valid CA cycle follows
ordinary Vegas and seeds history. Alpha/Beta retain learned values through
recovery. Record every adaptive decision for an independent rule audit.

Initial matched tests: supplied LEO solo and fixed 90ms propagation with CUBIC
joining at 80s; 200s, 100Mbps, queue100, seed123456789, no pacing, 100GB.
Both baseline and adaptive use the same new binary, renewal off. Check the
baseline against PR14's originals. Expand to solo 90->96ms step and fixed solo
only if the initial results justify explaining the mechanism. No parameter
sweep or selective tuning. Compare app delivery, common-window sharing,
direct micro queue delay/occupancy, drops, retransmissions and state traces.
Replay a representative case in a new volume, archive raw inputs with hashes,
and publish compact evidence plus the full final patch. No merge authorized.

## Completed result

Eight primary cases and a fresh fixed-competition replay completed. See the
[experiment record](../../docs/experiments/20261011-vegas-adaptive.md),
[all window/flow results](evidence/results.csv), and [figure](evidence/figures/comparison.png).
LEO goodput is 41.5113→50.2036 Mbps, less than renewal's 69.3432. Fixed
competition gives higher aggregate service and lower mean queue wait but worse
Jain sharing: .9618→.8275. Fixed solo also improves, so this is broader CA
adaptation rather than a route-specific reference correction. The candidate
remains separate; PR14 v1 is my preferred primary LEO study, not a team choice.

## Fresh-volume reproduction (PowerShell)

Use a **new ordinary clone**, container and volume. The current branch adds
post-hoc analysis/documentation; pin the actual simulation launch commit for
source-identical replay. Apply only the complete final `ns3.patch`, not both
patch files. `pr14-base.patch` plus `implement.py` are development provenance.

```powershell
git clone --branch experiment/vegas-adaptive-ca https://github.com/Jeongmin07/CS30401-Lab1.git vegas-adaptive-replay
Set-Location vegas-adaptive-replay
git checkout --detach 7ac0751235dc1ecb14b3042622ac50990429f17c
$studyRoot = (Resolve-Path .).Path
$studyGit = (git rev-parse --absolute-git-dir).Trim()
$studyImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
$studyContainer = 'vegas-adaptive-replay'
docker run -d --name $studyContainer --mount "type=bind,source=$studyRoot,target=/work,readonly" --mount "type=bind,source=$studyGit,target=/git-common/worktrees/vegas-adaptive-study,readonly" --mount 'type=volume,source=vegas-adaptive-replay-ns3,target=/home/ubuntu/ns-3.48' $studyImage sleep infinity
docker exec -w /home/ubuntu/ns-3.48 $studyContainer bash -lc 'git apply --check /work/code/vegas-adaptive/ns3.patch && git apply /work/code/vegas-adaptive/ns3.patch && git add -A && ./ns3 build -j 4'
docker exec $studyContainer python3 /work/code/vegas-adaptive/run_matrix.py --families leo fixed-comp fixed step --image-digest sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4 --out /tmp/cs30401-vegas/matrix-replay.json
```

The separate Git mount lets the launch runner read a Windows clone safely.
Our development checkout was a Git worktree: `/git-common` instead mounted
the parent repository's common `.git`, whose existing `worktrees/vegas-adaptive-study`
admin directory supplies the runner's same Git path. Both actual Docker volumes
applied the full committed patch and produced identical competition outputs.
The ordinary-clone mount variant above was checked separately before delivery.
Runners refuse existing case/output directories and record their launch commit;
do not change source midway through a matrix.

Analyze the newly reproduced original-source cases:

```powershell
foreach ($studyFamily in @('leo','fixed-comp','fixed','step')) {
  foreach ($studyMode in @('base','adaptive')) {
    $studyCase = "a1-$studyFamily-$studyMode"
    $studyArgs = @('/work/code/vegas-adaptive/analyze_vegas.py', "/tmp/cs30401-vegas/$studyCase", '--out', "/tmp/vegas-adaptive-analysis/$studyCase")
    if ($studyFamily -eq 'leo') { $studyArgs += @('--event-s','121.6','--event-s','187.4') }
    if ($studyFamily -eq 'fixed-comp') { $studyArgs += @('--window','common:80:200') }
    if ($studyFamily -eq 'step') { $studyArgs += @('--window','pre100:0:100','--window','post100:100:200') }
    docker exec $studyContainer python3 @studyArgs
    if ($LASTEXITCODE -ne 0) { throw "Analysis failed: $studyCase" }
  }
}
```

Use post-hoc `audit_adaptive.py`, `check_baselines.py`, `export_results.py` and
the reference receipts from this PR's completed branch, copying them into
`/tmp` with `docker cp` if using the pinned source checkout. Audit `--runs`
accepts completed run directories; `--compare OLD NEW` checks measurement CSVs
and source/binary/library/policy/network identities, ignoring wall-clock timing.
For comparing the same named case from two containers, first copy one completed
run tree into a new directory visible to the other container. Do not copy an
in-progress run or change raw files.

`check_baselines.py --reference-root RECEIPTS --root RUN_ROOT --out NEW_JSON`
reads the four compact PR14 receipts in `evidence/pr14-baselines`, validates
network parameters, and checks all 75 original baseline measurement files.
`export_results.py --runs RUN_ROOT --analysis ANALYSIS_ROOT --out NEW_FOLDER`
requires the original launch commit for source-identical primary publication.
The analyzer and exporter use exact half-open windows and ordered app payload;
queue wait includes zero-wait served dequeues, while pending packets are censored.
Whole-run sharing is not computed when a competitor starts late.

To regenerate the figure from the published compact tables, use this completed
branch in a writable container: `uv sync --frozen` in `code/kim-study`, then
`uv run --frozen python /work/code/vegas-adaptive/plot_results.py` there. This
reuses the repository's existing locked plotting dependencies; no production
dependency was added. PNG/PDF source hashes are in `evidence/figures/sources.json`.
The archive helper can attach full analyses/replay/audits, inventories every
selected original file, and independently streams every compressed member.
The [raw release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-adaptive-20261011)
and `evidence/raw-archive-receipt.json` identify the original data.
