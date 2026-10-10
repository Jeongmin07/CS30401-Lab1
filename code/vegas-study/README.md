# Vegas RTT-reference renewal experiment

For the narrowed v1 research question, start with the [English research brief and figures](report/RESEARCH_BRIEF.md), [regeneration instructions](report/README.md), and [paper-based alternative selection](../../docs/research/20261010-vegas-scope-and-alternatives.md). These reorganize existing evidence; no new simulations or TCP changes are included.

This is kim-seongchan's bounded follow-up to [PR13](https://github.com/Jeongmin07/CS30401-Lab1/pull/13), shared in [PR14](https://github.com/Jeongmin07/CS30401-Lab1/pull/14). Three teammates use separate AI chats and laptops. These files make one person's code, observations and limits reviewable; they do not assign other teammates work or select the team's final topic.

Read the [experiment note](../../docs/experiments/20261010-vegas-rtt-renewal.md) for results and interpretation. The question is whether retiring an old Vegas RTT reference restores delivery under changing propagation delay, and what happens when persistent queueing causes the same signal.

## What changes

`RecentMinRenewal=false` retains the original ns-3.48 Vegas decisions. When enabled, completed valid congestion-avoidance cycles contribute their minimum existing socket **SRTT** to a history. With 20 cycles present, the reference rises to that history's minimum if the rise is at least 1 ms. History then clears. Invalid cycles and Vegas disable/enable clear history. The current cycle is included, so the new reference cannot exceed its minimum SRTT. This retains ordinary downward minimum updates, slow-start rules, loss recovery and the original +/-1-MSS congestion-avoidance adjustment. It does not directly boost cwnd or obtain route information.

Twenty means **20 valid ACK-boundary Vegas cycles**, not exactly 20 RTTs, independent samples or 20 packets. The measured history elapsed time is recorded. The constants 20 and 1 ms are exploratory choices declared before this matrix; they are not an optimum or a safety guarantee. Queue delay can enter this reference, and the competition controls demonstrate that limitation. The LEO run also renews during early congestion avoidance, so whole-run gain includes early CA reference adjustment.

`vegas_state.csv` records actual minimum/reference, sample count, cwnd, threshold, diff, announced congestion state, history and each renewal. The new two-node driver records actual channel delay and socket types, application delivery, queue Enqueue-to-Dequeue wait, occupancy, pending packets and hook coverage. Trace hooks observe existing events; startup socket-class assertions use observation-only checks at start+1 ns. Existing transmission/drop/application observers are reused from the main branch's `code/kim-study/` patch; its experimental CUBIC threshold protection is not enabled by these runs.

## Files and patch choice

| File | Purpose |
| --- | --- |
| `ns3.patch` | Complete patch exported by the official `make_patch.sh`, relative to pristine `cs30401-base` |
| `vegas-overlay.patch` | Incremental Vegas and new-driver changes for a tree already carrying the exact main-branch canonical `code/kim-study/ns3.patch` |
| `vegas_micro.cc` | Source copy of the two-node control driver included in both patches |
| `run_case.py`, `run_matrix.py` | Refuse reused output IDs and dirty launch checkout; record exact source, patch, binary, shared-library, settings, command and runtime identities |
| `analyze_vegas.py` | Independent application sums, internal-state checks, actual queue distributions/occupancy and loss/terminal metrics |
| `analyze_matrix.py`, `export_evidence.py` | Reproducible full analysis and compact Git evidence |
| `audit_mechanism.py` | Independent reconstruction of the original v1 cycle history, queue windows and off/on trace prefixes |
| `archive_raw.py` | Compress completed run trees outside Git and independently verify every archived member's bytes/hash |
| `evidence/` | Small launch/configuration/analysis records and result tables; original packet logs are in the linked release |

Apply **one complete patch** to a fresh tree, or the original canonical patch followed by **one overlay**. Do not apply both complete and incremental variants. The complete patch SHA256 is `25ac4286f68373ee4e33d43f5f00e8676a65fc9c8747d65f643cd0fc28202f59`. The prerequisite canonical patch SHA256 is `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`. Existing studies and their patches are preserved.

## Fresh official environment and simulation

Run from a clean checkout of this PR's branch/review commit, with Docker running. Primary simulations used source commit `82ad34a975d4b15f8a536527f8ea4f0cf6e41624`; later analysis/documentation commits do not change that recorded launch identity. The following PowerShell example uses **new names for an empty volume and container**. Mounting the fresh volume copies the image's initialized official ns-3 tree, modules and `cs30401-base` Git tag. Reusing a modified volume can invalidate the comparison.

```powershell
$studyImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
$studyLaunchCommit = (git rev-parse HEAD).Trim()
$studyContainer = 'vegas-review'
$studyVolume = 'vegas-review-ns3'
docker volume create $studyVolume
docker run -d --name $studyContainer --mount "type=bind,source=$PWD,target=/work" --mount "type=volume,source=$studyVolume,target=/home/ubuntu/ns-3.48" $studyImage sleep infinity
docker inspect $studyContainer --format '{{.Image}}'
docker exec -w /home/ubuntu/ns-3.48 $studyContainer git status --short
docker exec -w /home/ubuntu/ns-3.48 $studyContainer git apply --index /work/code/vegas-study/ns3.patch
docker exec -w /home/ubuntu/ns-3.48 $studyContainer ./ns3 build
docker exec $studyContainer python3 /work/code/vegas-study/run_matrix.py --prefix review-v1 --out /tmp/cs30401-vegas/matrix-review-v1.json --workers 2 --image-digest sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4
```

Check the inspected image identity equals the pinned SHA before running. The runner handles Git's Windows bind-mount ownership and CRLF normalization locally without changing host Git settings. Its live staged patch and driver must match the committed artifacts. It fingerprints all ns-3 shared libraries as well as the executable, since the executable alone does not identify the TCP implementation.

The matrix declares ten 200-second runs before launching: fixed solo, +6-ms RTT step solo, fixed plus CUBIC, step plus CUBIC, and supplied LEO; each has renewal off/on. Micro controls have a 100-Mbit/s full-duplex link, 100-packet FIFO per direction, initial one-way delay 45 ms, and a 100-s no-op or rise to 48 ms. CUBIC starts at 80 s on the same forward device queue. Each flow requests 100 GB, MSS 1380, initial cwnd 10, initial micro ssthresh 900 MSS, 32-MiB TCP buffers, no pacing or error model, seed 123456789/run 1. The driver removes root queue discs and checks their absence and the actual Vegas/CUBIC socket types. LEO uses the unmodified supplied Seoul 1584 to London 1585 state, official defaults and 100-Mbit/s ISL/GSL, queue 100, one 100-GB Vegas flow over 200 s. Micro-only parameters are excluded from LEO declarations.

To run just the LEO pair, add `--only leo` and use a new prefix/record path. To change a parameter, use `run_case.py` directly with a new ID, and label it a new experiment rather than a replay of v1. Remaining defaults are in the unchanged course ns-3.48 stack.

## Analyze and export

These commands run no simulations. Use a new output directory every time. For the primary v1 runs, the analysis helper is recorded at post-hoc commit `21f828a` (full identity is in `evidence/`), separately from the simulation launch `82ad34a`. For a newly launched `review-v1` matrix, replace the prefix and supply that checkout's full launch commit. The wrapper checks each case's actual condition and launch identity before analyzing.

```powershell
docker exec $studyContainer python3 /work/code/vegas-study/analyze_matrix.py --prefix review-v1 --launch-commit $studyLaunchCommit --root /tmp/cs30401-vegas --out /tmp/vegas-review-analysis --workers 2
docker exec $studyContainer python3 /work/code/vegas-study/export_evidence.py --analysis-root /tmp/vegas-review-analysis --out /tmp/vegas-review-evidence
docker exec $studyContainer python3 /work/code/vegas-study/archive_raw.py --root /tmp/cs30401-vegas --pattern 'review-v1-*' --extra matrix-review-v1.json --attach-tree analysis=/tmp/vegas-review-analysis --out /tmp/vegas-review-raw.tar.gz
```

For an individual case, `analyze_vegas.py RUN --out NEW_DIR` works directly. The matrix first runs the original `code/kim-study/analyze_study.py` with bins, then cross-checks its delivery totals/bins with the independent analyzer. LEO event windows use 121.6 and 187.4 s; micro uses 100 s. Competition also uses the common 80–200-s window. The fixed-competition first-false-renew history window is declared explicitly and the same in both modes. Each analysis phase keeps commands, source fingerprints, console status and elapsed time. Export independently recounts TcDrop by flow/layer and fingerprints all original run files; it copies small original manifests/configs without relabeling them.

`archive_raw.py` includes the per-file inventory and verifies every compressed member against original bytes/SHA256, then writes an archive receipt. The recorded primary archive/release identity is linked from the experiment note. `docker cp` can copy the resulting small export directory and large archive to separate host output folders; only the compact export belongs in Git.

`audit_mechanism.py` audits the **original v1 matrix** (fixed case IDs and original launch identity), independently of the two analyzers. After extracting the raw release into a new root, run `python3 audit_mechanism.py --root EXTRACTED_RUN_ROOT --out NEW_JSON`. It reads existing traces, not ns-3. The installed ns-3 source should still carry this exact patch for its source checks. The recorded [audit](evidence/mechanism-audit.json) and [execution](evidence/mechanism-execution.json) are separate post-hoc artifacts; they were authored after the raw archive and are supplied in Git rather than claimed to be inside its 380 members. The helper is not a generic assertion of different prefixes, policies or launch commits.

## Metrics, storage and interpretation

All delivered throughput here is unique, ordered payload accepted by the receiver application's `HandleRead`, not sender ACK progress or pre-TCP wire arrival. Windows use exact half-open `[start_ns,end_ns)`. Whole-run averages include startup. Competitor throughput over 80–200 s uses a 120-s denominator; never add it to foreground throughput averaged over 0–200 s. The common 80–200-s window provides comparable per-flow totals and Jain fairness. Receiver wire interval union and bytes still undelivered to the app at termination remain separate metrics.

Queue wait is measured directly from Enqueue to Dequeue, excluding link serialization/propagation. Packet means/p95 include zero-wait dequeues; pending packets are right-censored. Occupancy is time weighted. These queue measurements exist only in the micro controls. The LEO trace contains sender SRTT and drop coverage, not per-hop queue sojourn; SRTT minus geometric delay is not presented as measured queue waiting time.

With no root qdisc, a stopped device transmission queue causes `TrafficControlLayer::Send` to emit `TcDrop` before device queue admission. Thus `DropBeforeEnqueue=0` and `DropAfterDequeue=0` do **not** imply zero congestion losses. Read traffic-control drops, distinct tagged transmissions, retransmissions and recovery together. A TCP `CA_LOSS` entry is not automatically an RTO count.

The primary raw trees total about 7.54 GB before full analyses, despite these runs taking minutes rather than hours. Keep them outside Git. Publish compressed originals as release assets, including the member inventory, archive SHA256 and exact run identifiers. Course submission must exclude raw traces, generated state, full ns-3 trees and builds. These tools use Python's standard library; plotting/notebooks/TeX are not needed for the recorded metrics. This bundle is experiment evidence, not the final six-page report or team submission ZIP.

The mechanism is prior-informed. [La, Walrand and Anantharam (1999), §§3–4](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1999/Archive/ERL-99-3.pdf) study rerouting reference renewal and persistent congestion. Our 20-cycle/min-rise policy is a simplified ns-3-specific experiment, not their full algorithm or a new invention. [Gu and Zhang (2005)](https://pure.bit.edu.cn/en/publications/behavior-and-performance-improvement-of-tcp-vegas-in-leo-satellit/) already study Vegas path-change misclassification in LEO; only its institutional abstract/metadata have been read, so its exact method is not claimed reproduced. The contribution under consideration is measured mechanism/benefit/cost in the supplied model.
