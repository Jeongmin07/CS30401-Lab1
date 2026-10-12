# Finite-flow CUBIC HyStart diagnostic

Read [the completed six-case experiment](../../docs/experiments/20261012-orbit-hystart.md) and its linked compact evidence. The supplied HyStart **helped** the tested flow; disabling it increased losses and completion time. The predeclared forecast-window control had no qualifying exit to defer and reproduced baseline measurements. This does not justify blanket disabling or a general LEO improvement claim.

The official image is pinned in `run.py`. All cases are one 8 MiB flow, 100 Mbit/s, 1,000-packet queues, with the original TCP defaults. `--hystart` is parsed before setting the default and the actual sender's CUBIC type/attribute is checked. Passive logging records the exact original exit branches. Queue observations use actual packet-object identity, include zero waits, verify terminal conservation and report per-device visits rather than end-to-end delay. The generic queue observer was reused from `code/bbr-route/observability.py` without BBR state/control code.

Artifacts identify two source phases: `observed.patch` for the original on/off/stable cases, and `ns3.patch` for the final observer-off and forecast controls. Each is a **complete patch for clean official source**, including canonical v6. The initial `passive.patch` is a retained pre-queue draft and was not used in any reported simulation. Do not stack complete patches.

## Reproduce the measured phases

Run from the repository root in PowerShell with new container/volume/output names. Two CPUs and 4 GiB limit this track; compile with one job. The simulation runner refuses existing case folders, compares the installed diff with the selected patch, pins current libraries and records actual command, inputs, binary/library identities, status and raw hashes. Both flags are opt-in study controls; no kernel/RACK implementation is added.

```powershell
$hyRoot = (Resolve-Path .).Path
$hyImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
docker run -d --name hystart-replay --cpus 2 --memory 4g --mount "type=bind,source=$hyRoot,target=/work" --mount 'type=volume,source=hystart-replay-ns3,target=/home/ubuntu/ns-3.48' $hyImage sleep infinity

docker exec -w /home/ubuntu/ns-3.48 hystart-replay bash -lc 'git apply --check /work/code/orbit-hystart/observed.patch && git apply /work/code/orbit-hystart/observed.patch && git add -N scratch/main_satnet/study_drop_trace.h scratch/main_satnet/orbit_hystart_queue.h scratch/study_micro/study_micro.cc && ./ns3 build -j 1'
docker exec hystart-replay python3 -B /work/code/orbit-hystart/run.py near-on near-off stable-on stable-off --patch /work/code/orbit-hystart/observed.patch --timeout 240

# Replace the known, isolated source phase; raw cases remain outside the ns-3 volume.
docker exec -w /home/ubuntu/ns-3.48 hystart-replay bash -lc 'git apply --reverse --check /work/code/orbit-hystart/observed.patch && git apply --reverse /work/code/orbit-hystart/observed.patch && git apply --check /work/code/orbit-hystart/ns3.patch && git apply /work/code/orbit-hystart/ns3.patch && git add -N scratch/main_satnet/study_drop_trace.h scratch/main_satnet/orbit_hystart_queue.h scratch/study_micro/study_micro.cc && ./ns3 build -j 1'
docker exec hystart-replay python3 -B /work/code/orbit-hystart/run.py near-on-unobserved near-forecast --patch /work/code/orbit-hystart/ns3.patch --timeout 240

docker exec hystart-replay python3 -B /work/code/orbit-hystart/analyze.py near-on near-off stable-on stable-off near-on-unobserved near-forecast --out /tmp/hystart-export-new
docker exec hystart-replay python3 -B /work/code/orbit-hystart/archive.py --out /tmp/hystart-raw-new.tar.gz --receipt /tmp/hystart-raw-receipt-new.json
```

Only the original local workflow was executed here; this README's separate-volume full replay has not been run. Wall-clock timing and archive bytes are not expected to reproduce. Compare measured CSVs and source/condition identities. The passive comparison deliberately spans the two recorded source phases; it checks the combined inactive-policy/observer changes in one condition, not every possible trace path independently.

`install.py` develops the passive phase from a clean source by first applying exact canonical v6. `add_policy.py` develops the second phase from the exact `observed.patch` tree. Reproduction needs the exported patches above; no whole ns-3 tree or constellation state is shared. The narrow policy defers only an ACK-train-only exit inside `121600000000:121781136000`, retaining a simultaneous DELAY exit and all decisions outside. This oracle interval came from supplied geometry before measurement, not future packet delay. In the actual control it made zero deferrals.
