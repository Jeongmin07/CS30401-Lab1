# Reproduce Team 5's fixed CUBIC study

Authors: Seongchan Kim, Jeongmin Kim, Jaehwan Kang.

This code is self-contained. It uses the official `2026f-v1` course image, ns-3.48/course baseline commit `99bc6f733274475b7a6e804128651e17ee2a2536`, and the image's cached Seoul–London 200-second state. No other study directory, GitHub result download, topology generator or raw log is required. Use the pinned image below; two **new** source volumes keep the exact previously evaluated runtimes separate.

The primary proposed profile is **selective old-flight loss waiting plus the bounded final-packet allowance, pacing OFF**. The unchanged baseline disables both custom policies. Native pacing and backpressure are diagnostic options. No global default or new algorithm is introduced by this final package. The known-capacity ceiling helps the fixed bulk but slows the finite loss control; it is not the default profile.

## Apply, build and run

From the directory containing the submitted `README.md` and `code/`, create the two fresh containers. Choose unused container/volume names if these names already exist; do not reset another study's volume.

```sh
IMAGE=ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4
docker run -d --name lab1-final-pace --cpus 2 --memory 4g -v "$PWD:/work" -v cs30401-final-pace:/home/ubuntu/ns-3.48 --entrypoint bash "$IMAGE" -lc 'sleep infinity'
docker run -d --name lab1-final-bp --cpus 2 --memory 4g -v "$PWD:/work" -v cs30401-final-bp:/home/ubuntu/ns-3.48 --entrypoint bash "$IMAGE" -lc 'sleep infinity'
docker exec lab1-final-pace bash /work/code/run_all.sh pace
docker exec lab1-final-bp bash /work/code/run_all.sh bp
```

Inside this research repository, the corresponding script is `/work/code/lab1-final/run_all.sh`; in the submitted archive it is `/work/code/run_all.sh`. Everything else resolves relative to that script. On Windows PowerShell, replace `"$PWD:/work"` with the absolute submission-directory mount string.

`build.py` applies the exact `runtimes/pace.patch` or `runtimes/bp.patch` to a clean course baseline, invokes the official `make_patch.sh`, requires **byte-for-byte equality** of its exported patch and the frozen artifact, then builds synchronously with one job. It writes readiness, export and build logs outside `code/`. Source guards include staged and unstaged changes because the official helper stages new files. Each run has a 600-second wall cap and refuses an active build, stale source/runtime/readiness, existing output or changed package input/helper. Failures are preserved and stop the batch.

The pace runtime has 16 fixed physical conditions: ten core controls, native/capacity bulk diagnostics, selected paced micro, two startup first-loss controls, and the T75→T78 routing counterfactual. The BP runtime has its own three controls. The total is **19 physical runs / 22 named condition mappings**. Diagnostic pacing OFF aliases core `leo10-tail`; safety micro-original/current alias core `micro-base`/`micro-tail`. These are the same command/configuration on the same runtime, not extra simulations. Selective and tail bulk remain separate runs; BP control is a distinct runtime control. `common.py` is the exact case/alias map.

Typical simulation execution is under a second per 4-second micro and approximately 30–60 seconds per 200-second LEO run on this machine; actual wall times are recorded. Fresh builds and input/output hashing are additional. CPU/memory availability can change these times. Two builds may run sequentially if host memory is limited. No parameter sweep or four historical BBR/HyStart/hold candidate rebuild is included.

## Regenerate figure and table inputs

After both profiles finish, merge their **freshly computed** inputs and render the report figures:

```sh
docker exec lab1-final-pace python3 -B /work/code/merge.py --pace /work/output/lab1-final-replay/pace/report-data.json --bp /work/output/lab1-final-replay/bp/report-data.json --out /work/output/lab1-final-replay/report-data.json
docker exec lab1-final-pace uv sync --project /work/code --frozen
docker exec lab1-final-pace uv run --project /work/code python /work/code/report/build_figures.py --data /work/output/lab1-final-replay/report-data.json --out /work/output/lab1-final-replay/figures
```

The checked-in `pyproject.toml`/`uv.lock` pins plotting dependencies; all runner/analysis/validation tools use the Python standard library. Figure1 uses actual cwnd state near T26.2, Figure2 the four observed finite FCTs, and Figure3 the source's exact 100-ms queue-state integrals over `[74.5,77.5)`. The report's core result tables use `cases[*].metrics` and `windows.first/legacy`; queue diagnostics use source/all-device queue fields plus actual loss/recovery counts. True-loss tables use the exact physical-drop/original-TX and post-drop RETX join. The report role mapping and every underlying file receipt are in the merged JSON. A figure/table command map is completed with the manuscript in `report/`.

`inputs/expected-parity.json` retains the original 345 historical measurement contracts and scalar references, **not raw logs or plotting data**. Analysis reads fresh traces and requires 342 measurement CSVs to match byte-for-byte. The three BP `bp_outcomes.csv` files use the additional `inputs/expected-pending-order.json` contract: header and ordered non-pending bytes are exact, and all 15 fields of every terminal pending row, including multiplicities, must match exactly; only the order of this final suffix may differ. The observer writes that suffix from a pointer-keyed map, so independent builds can serialize it in a different order. The initial strict BP analysis failure is retained as a postprocessing attempt; no simulation or policy was rerun to repair it. Wall profiling is excluded. The counterfactual must match its natural selective control before T75. The submitted archive excludes generated state, raw simulation logs, ns-3 trees and build artifacts; fresh outputs are written to `/tmp` and `/work/output`.

## Model, parameters and reuse

Core LEO conditions use CUBIC/SACK/PRR, provided 1584-satellite/2-ground-station routing, 100-ms updates, fixed10 Mbps ISL/GSL, q100, seed123456789, one100 GB flow at0, and duration200 s. The model has instant switches and no random wireless loss/outage/capacity variation. Micro controls use fixed50 ms one-way propagation, physical100 Mbps/q2000,20 or21 MSS, an actual first-segment loss and the existing deliberately incorrect hint. The geometry input supplies same-T directional path delays; controller parameters are unchanged copies of the frozen policy. Drop models are evaluation-only and are not controller hints.

The T75→T78 control invokes the original deterministic `delay_route.py` on cached state. It modifies exactly two sparse route files, validates accumulated state and all affected forwarding paths against fresh native interface metadata, retains the original forecast epochs, and makes no shortest-path or topology calculation. Its ideal-channel intervention is not proof of physical handover feasibility.

Pacing uses native ratios200%/120%, initial-window pacingfalse, and the fixed payload ceiling `floor(link_bps*1380/1434)`:9,623,430 bps for10 Mbps and96,234,309 bps for the selected100 Mbps micro. These are ceilings, not forced rates. Initial bursts/direct retransmissions prevent strict wire shaping. BP uses the original device100p control, FIFO96p+device4p, or stock CoDel96p+device4p; requeued/serializing packets are measured separately. All are copied evaluated settings, not new defaults or tuned rates.

We reuse and acknowledge the course environment's scenario, applications, cached state, helpers and ns-3 CUBIC/SACK/PRR/native pacing/FIFO/CoDel implementations. The submitted patches add the team's bounded loss-wait/tail mechanism, deterministic evaluation controls and passive trace instrumentation. `copied-sources.json` identifies unchanged study-helper snapshots. Cite Hypatia: S. Kassing et al., “Exploring the ‘Internet from space’ with Hypatia,” ACM IMC,2020. Additional related-work references and limits are in the report.
