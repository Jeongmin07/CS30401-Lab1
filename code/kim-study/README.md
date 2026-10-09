# Independent TCP study — kim-seongchan

Read [EXPERIMENT_NOTE.md](EXPERIMENT_NOTE.md) for the mechanism, all 23 configurations, benefits and failure conditions. This is an independent exploratory result, not a team decision or the final submission. Teammates' experiment outputs are not inputs.

The primary question is: **when does route-related packet reordering cause unnecessary recovery in the course CUBIC/SACK/PRR implementation, and what benefit and real-loss cost follow from selectively increasing its packet-count loss threshold?** Related subquestions cover notification timing, queue size, link rate, and short-flow completion. [RESEARCH_PLAN.md](RESEARCH_PLAN.md) records alternative Vegas and BBR candidates and the evidence still needed. The handout allows one or more problems and ideas; it does not require one research question.

## Read the evidence

- [All 23 result rows](evidence/results.csv): receiver application goodput, observed tagged drops, retransmissions, patch hashes and measured run time.
- [Per-case manifests and compact summaries](evidence/cases): exact parameters/commands, config and schedule when applicable, metrics, hook coverage and bounded packet examples.
- [Publication manifest](evidence/publication_manifest.json), [original matrix record](matrix_execution.json), and [fresh-volume v4 reproduction](reproduction_v4.json).
- [Complete v5 replay check](evidence/reproduction_v5.json) and [replayed case manifests](evidence/replay_case_manifests_v5.json): all 23 configurations, 184 raw/legacy inputs and 23 full analysis files match byte for byte in a separately initialized volume. Five figures were regenerated; rendered image-byte equality is not asserted.
- [Figures](figures/v4) and [short-flow counterexample](figures/tail-v5), each as PNG/PDF with figure-source hashes.
- [Source-row evidence for the 26.2-second mechanism](evidence/event26_evidence.csv), including covering ACK timing and the forwarding-snapshot control.

Compact summaries omit time bins and some event examples; their `publication_export` fields identify omissions, the full-analysis hash, and SHA-256/size of raw inputs. Figures were generated from the full local analysis and raw traces. Raw traces are **not** in Git: on the original machine they remain in `/tmp/cs30401-study/<case>/logs_ns3` in container `cs30401-kim-study`. To regenerate figures on another machine, first rerun and analyze the experiments below. Nothing here depends on the repository's `shared-results` directory.

## Reproduce in a new Docker volume

Run these PowerShell commands from the repository root. Use a new container name and empty volume; existing run directories are deliberately never overwritten. The image digest pins the supplied course environment, not a newly generated network state.

```powershell
$studyRoot = (Resolve-Path .\code\kim-study).Path
$studyImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
docker run -d --name kim-study-replay --mount "type=bind,source=$studyRoot,target=/work" --mount 'type=volume,source=kim-study-replay-ns3-v5,target=/home/ubuntu/ns-3.48' $studyImage sleep infinity
docker exec -w /home/ubuntu/ns-3.48 kim-study-replay bash -lc 'git apply --check /work/ns3.patch && git apply /work/ns3.patch && ./ns3 build'
docker exec kim-study-replay bash /home/ubuntu/lab/scripts/check_env.sh
docker exec kim-study-replay python3 /work/make_state_control.py
docker exec kim-study-replay python3 /home/ubuntu/lab/scripts/path_truth.py /home/ubuntu/lab/data/seoul_london/state dynamic_state_100ms_for_200s 1584 1585 /work/path_truth_200s.csv
docker exec kim-study-replay python3 /home/ubuntu/lab/scripts/path_truth.py /tmp/cs30401-controls/delay26/state dynamic_state_100ms_for_200s 1584 1585 /work/path_truth_delay26.csv
docker exec kim-study-replay python3 /work/replay_cases.py --workers 3
docker exec kim-study-replay python3 /work/analyze_replay.py
docker exec kim-study-replay python3 /work/compare_replay.py --out /work/reproduction_v5.json
docker exec kim-study-replay python3 /work/export_evidence.py --execution-record /work/replay_execution.json --out /work/evidence-replayed
docker exec kim-study-replay python3 /work/extract_event26.py --output /work/event26_replayed.csv
```

`replay_cases.py` reads committed manifests and executes all 23 parameter configurations; `analyze_replay.py` preserves their declared event definitions. `compare_replay.py` checks full raw input and full analysis hashes. `export_evidence.py` regenerates the complete table as `evidence-replayed/results.csv`, keeping newly measured runtime/patch provenance separate from published evidence; it refuses an existing output directory. `extract_event26.py` regenerates and validates the packet/ACK evidence excerpt. These commands map the report's table and event timestamps to executable code.

A subset can be selected, for example `python3 /work/replay_cases.py leo10-base leo10-guard20 --workers 1`; analyze it normally, but the full comparison/table/event commands require their referenced cases to exist. The routing-timing control requires `make_state_control.py` first; all other LEO runs use the unmodified official Seoul–London state.

The original 20-case matrix took **278.014 seconds wall time**, with at most three concurrent simulations on Docker allocated 12 CPUs and approximately 8.15 GB RAM. Individual measured times are in manifests. Build, environment check, analysis and rendering are additional. This is a hardware-specific measurement, not a runtime guarantee. Deterministic configurations are not independent statistical replicates.

The original matrix used [study-v4.patch](study-v4.patch), SHA-256 `b4189c7689379a523decf564605b055e836981f948d8ca6e662cbe81dd8fbf99`. The canonical [ns3.patch](ns3.patch), version 5, SHA-256 `b5657a3b2919ed32ea7fcb8f14a922a75a94cc4d9910e99f809c771747cff3e6`, only additionally exposes the microbenchmark's `max_bytes` command-line argument for the short-flow controls. Its default remains 100 GB. Do not apply both patches to the same source tree. For exact version-4 matrix replay, apply only `study-v4.patch` on a separate clean volume and pass `--patch /work/study-v4.patch`; exclude the two short-flow version-5 cases. Patch selection in the runner records provenance; it does not apply or verify the installed source patch for you.

## Render publication figures

Only plotting needs external Python packages. The locked dependencies are Matplotlib 3.10.8 and NumPy 2.4.4; simulation orchestration and analysis use Python's standard library. After replay and analysis:

```powershell
docker exec -w /work kim-study-replay uv sync --frozen
docker exec -w /work kim-study-replay uv run --frozen python /work/plot_study.py --drop-layer PhyRxDrop --stage 'reproduced configurations, v5' --out /work/figures/replayed
docker exec -w /work kim-study-replay uv run --frozen python /work/plot_study.py --only loss --loss micro-tail-base-v5 micro-tail-guard20-v5 --drop-layer PhyRxDrop --loss-completion-bytes 27600 --loss-title 'Short-flow actual-loss counterexample' --stage 'reproduced short-flow controls, v5' --out /work/figures/replayed-tail
```

Figure mapping: `route_event_causal` shows the declared 26.2-second episode; `receiver_goodput_comparison` contrasts full-run and event-window effects; `stable_path_loss_recovery` isolates the injected physical receive drop; `candidate_baseline_traces` shows CUBIC, Vegas and BBR probes. The short-flow version adds completion time for all 27,600 application bytes. Axes and labels distinguish measured SRTT, receiver delivery and cwnd. No synthetic measurements or confidence intervals are supplied.

## Source changes and limits

The patch adds opt-in transmission identity, receiver delivery/state/drop traces and a two-node control benchmark. In detailed flow logging mode, `CS30401_STUDY_TRACE=1` enables the new traces. Existing legacy traces were byte-identical with instrumentation disabled/enabled in the checked pilot. The experimental controller uses schedule `AdditionalParameters`, for example:

```text
study_threshold=20;study_windows=26100000000:26500000000|74900000000:75300000000
```

Thresholds affect both duplicate-ACK handling and SACK packet-count presumed-loss marking. A larger threshold does not clear already marked losses. Restoration is deferred until a permitted final congestion state; the effective protection may exceed its requested interval. Actual durations and deadline misses are reported. Notifications in these experiments are oracle information; a deployable notification path, its error and cost have not been implemented.

`make_state_control.py` creates symlinks under `/tmp/cs30401-controls` and replaces only its own forwarding-file links at 26.2–26.8 seconds with the 26.1-second snapshot. It does not edit the official state or freeze satellite movement. `path_truth_*.csv` are small derived path diagnostics, not generated constellation state directories.

ns-3.48's tested CUBIC/SACK/PRR implementation lacks RACK-TLP. Observed receiver wire arrival alone is not proof of application acceptance; the analyzer requires positive acceptance evidence. Hook coverage is checked, including `TrafficControlLayer::Drop` before device queue admission and root queue-disc absence. This does not audit every possible receiver TCP rejection path. Every conclusion must retain the stack and scenario scope described in the note.

Reordering protection is existing prior art. The references in the experiment note distinguish earlier mechanisms from the proposed selective activation study. The code uses the official course/Hypatia environment and ns-3 APIs, with GPT-assisted modifications; neither code nor measurements should be described as an independently invented TCP stack.

## Final report and submission constraints

The English report must use the unchanged IEEE conference two-column, 10-point Times template, Team ID and all names under the title, and the six requested sections: Introduction, Problem Statement, Proposed Idea(s), Experiment Setup, Evaluation, Conclusion. It is limited to six pages excluding references/appendix. For this study, lead with one validated mechanism and use related subquestions to establish the benefit/cost boundary; multiple unrelated weak claims would consume that space without stronger evidence.

Problem, idea, soundness, reproducibility, clarity and presentation are the six stated grading dimensions; the handout assigns no numeric weights. A small measured gain can be defensible when the TCP mechanism, baseline, information assumptions, counterexamples and reproducibility are convincing. Current incomplete candidates must remain hypotheses.

The final `Lab1_{TeamID}.zip` must contain `report.pdf`, `README.md`, `code/`, reproducible commands/runtime/figure mapping, and `pyproject.toml` plus `uv.lock` for Python dependencies. Generate the final patch using the official `make_patch.sh`, for example `docker exec kim-study-replay bash /home/ubuntu/lab/scripts/make_patch.sh /work/ns3.patch`. Exclude state, raw traces, raw trace excerpts, the ns-3 source tree and builds; regenerate review excerpts with the included script. This folder is an experiment bundle, **not** that final submission ZIP. Team identity, common scope, the final report, multi-flow/other-path validation and presentation remain to be completed.
