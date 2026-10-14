# Bounded ELT screening

See [RESULTS.md](RESULTS.md) for all 19 measured comparisons and limits. This is a supplemental opt-in experiment on top of PR #16, not a change to the prior submission. Source checkpoint is `44f0850c2eb0fe3127993601822a55f502dfbd05`; model patch SHA is `8f822979eb9556c1f27f5128a462d66f085b1554ab3366c9af2c4036df8d7997`.

Use the pinned official image and a **new source volume**. Do not apply this patch on top of an already modified earlier volume. The full patch includes the frozen dependency plus the ELT overlay; `implement.py` is an optional audited generator from exact ace08 sources, not needed for normal replay.

From a local clone containing this directory, launch a new container (PowerShell example):

```powershell
docker run -d --name lab1-elt-replay --cpus 2 --memory 4g --mount "type=bind,source=$($PWD.Path),target=/work" --mount "type=volume,source=lab1-elt-replay-fresh,target=/home/ubuntu/ns-3.48" ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4 sleep infinity
docker exec lab1-elt-replay git -C /home/ubuntu/ns-3.48 apply --check /work/code/orbit-elt/ns3.patch
docker exec lab1-elt-replay git -C /home/ubuntu/ns-3.48 apply /work/code/orbit-elt/ns3.patch
docker exec lab1-elt-replay python3 -B /work/code/orbit-elt/build.py --out /tmp/elt-replay-ready.json
docker exec lab1-elt-replay python3 -B /work/code/orbit-elt/run.py --root /tmp/elt-replay --ready /tmp/elt-replay-ready.json --checkpoint 44f0850c2eb0fe3127993601822a55f502dfbd05
docker exec lab1-elt-replay python3 -B /work/code/orbit-elt/analyze.py --root /tmp/elt-replay --out /tmp/elt-replay-analysis
docker exec lab1-elt-replay python3 -B /work/code/orbit-elt/check_off_parity.py --root /tmp/elt-replay --out /tmp/elt-replay-parity.json
```

Use unique names for each container/volume/output directory. The runner refuses overwritten attempts and stops on failures, runtime/source/input changes. Default dispatch is all 19 predeclared physical conditions. `--cases micro21-stock micro21-tail micro21-eltA micro21-eltC` selects a quick finite subset; keep its results separate from a full matrix. Model mode0 preserves the chosen prior tail configuration; mode1 is Aggressive, mode2 Careful. Both ELT modes disable tail admission and all measured cases have pacing off.

`build.py` verifies the official HEAD, full staged+unstaged diff, official patch export and completed runtime hashes. The Windows worktree's absolute `.git` target may be inaccessible from a Linux bind mount; this is explicitly qualified in manifests instead of reporting a fabricated launch commit. Source checkpoint is host-declared and every launch verifies exact source/input/binary hashes.

The checked-in `results/summary.csv` is the compact comparison table; `metrics.json` includes completion, physical-loss and policy audits. Full per-case manifests/configs, all raw traces, detailed analysis and successful/failed build records are supplied in the release archive linked below. Full detailed objects are kept out of Git to avoid repeating tens of MB of evidence.

Finite-file FCT uses complete ordered APP delivery. The CSV's whole-window goodput divides by the full four-second simulation, including idle time after completion; it is not finite-transfer average speed. Bulk whole-window goodput divides by 200 seconds. All event windows are half-open.

[Verified experiment assets](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/orbit-elt-screen-20261014). The raw archive is 64,887,523 bytes; SHA-256 `8895c2d79000e31d165fe2af689e0599e17aaff26902b5bb119dc9471bc45bc0`. GitHub's uploaded asset digest matches the local digest. Its `orbit-elt-v2/` directory contains exactly the 19 successful runs; `orbit-elt/` is the pre-simulation failed launch and `orbit-elt-build-attempt1/` is preserved first-build evidence. Detailed analysis is under `results/`.
