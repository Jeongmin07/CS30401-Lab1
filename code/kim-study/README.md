# Independent TCP study — kim-seongchan

Read [EXPERIMENT_NOTE.md](EXPERIMENT_NOTE.md) for the initial 23 cases and [PHASE2_NOTE.md](PHASE2_NOTE.md) for 52 subsequent cases, finite-flow exemption and notification timing. The bundle records **75 declared cases**, including regressions that overlap earlier conditions; these are not 75 independent unique conditions or statistical seed replicates. This is independent exploratory work, not a team decision or the final submission. Teammates' experiment outputs are not inputs.

The primary question is: **when does route-related packet reordering cause unnecessary recovery in the course CUBIC/SACK/PRR implementation, and what benefit and real-loss cost follow from selectively increasing its packet-count loss threshold?** Related subquestions cover notification timing, queue size, link rate, and finite-flow completion. [PARAMETER_AND_DEPLOYMENT_NOTE.md](PARAMETER_AND_DEPLOYMENT_NOTE.md) supplies parameter bases and information/deployment assumptions; [RELATED_WORK_NOTE.md](RELATED_WORK_NOTE.md) and [RESEARCH_PLAN.md](RESEARCH_PLAN.md) distinguish prior work and alternative candidates. The handout allows one or more problems and ideas; it does not require one research question.

## Read the evidence

- [Initial 23 result rows](evidence/results.csv): receiver application goodput, observed tagged drops, retransmissions, patch hashes and measured run time.
- [Phase-two CSV](phase2_results.csv), [JSON](phase2_results.json) and [52-case execution record](phase2_execution.json): finite-flow completion, bypass activation, loss/recovery counts, exact commands and parameter families.
- [All 75 per-case manifests and compact summaries](evidence/cases): exact parameters/commands, config and schedule when applicable, metrics, hook coverage and bounded packet examples.
- [Initial publication manifest](evidence/publication_manifest.json), [original matrix record](matrix_execution.json), and [historical single-case v4 reproduction](reproduction_v4.json).
- [Historical complete v5 replay check](evidence/reproduction_v5.json) and [v5 replayed case manifests](evidence/replay_case_manifests_v5.json): the initial 23 cases, 184 raw/legacy inputs and 23 full analysis files match byte for byte in a separately initialized volume. Five figures were regenerated; rendered image-byte equality is not asserted. This record does not verify phase two or version 6.
- [Complete fresh-volume v6 comparison](evidence/reproduction_v6.json): all 75 declared cases succeed; 600 raw/legacy inputs and 75 full analysis files match byte for byte. These checks establish deterministic reproduction of the recorded cases, not additional independent samples or generality to other TCP stacks.
- [Figures](figures/v4) and [short-flow counterexample](figures/tail-v5), each as PNG/PDF with figure-source hashes.
- [Phase-two figures](figures/phase2) and [their source manifest](figures/phase2/figure_sources.json): finite loss, window offsets and the matched 80-MSS delay control.
- [Source-row evidence for the 26.2-second mechanism](evidence/event26_evidence.csv), including covering ACK timing and the forwarding-snapshot control.

Compact summaries omit time bins and some event examples; their `publication_export` fields identify omissions, the full-analysis hash, and SHA-256/size of raw inputs. Figures were generated from the full local analysis and raw traces. Raw traces are **not** in Git: on the original machine they remain in `/tmp/cs30401-study/<case>/logs_ns3` in container `cs30401-kim-study`. To regenerate figures on another machine, first rerun and analyze the experiments below. Nothing here depends on the repository's `shared-results` directory.

The canonical version-6 patch was built in `cs30401-kim-repro-v6`, using a new volume initialized from unmodified official source. All 75 simulations and their analyses completed successfully. The recorded comparison reports **600 raw/legacy input files and all 75 full analysis JSON files byte-identical** to the original evidence. It does not independently prove that every loss path is instrumented, establish statistical confidence or compare rendered-image bytes.

## Reproduce in a new Docker volume

Run these PowerShell commands from the repository root. Use a new container name and empty volume; existing run directories are deliberately never overwritten. The image digest pins the supplied course environment, not a newly generated network state.

```powershell
$studyRoot = (Resolve-Path .\code\kim-study).Path
$studyImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
docker run -d --name kim-study-replay --mount "type=bind,source=$studyRoot,target=/work" --mount 'type=volume,source=kim-study-replay-ns3-v6,target=/home/ubuntu/ns-3.48' $studyImage sleep infinity
docker exec -w /home/ubuntu/ns-3.48 kim-study-replay bash -lc 'git apply --check /work/ns3.patch && git apply /work/ns3.patch && ./ns3 build'
docker exec kim-study-replay bash /home/ubuntu/lab/scripts/check_env.sh
docker exec kim-study-replay python3 /work/make_state_control.py
docker exec kim-study-replay python3 /home/ubuntu/lab/scripts/path_truth.py /home/ubuntu/lab/data/seoul_london/state dynamic_state_100ms_for_200s 1584 1585 /work/path_truth_200s.csv
docker exec kim-study-replay python3 /home/ubuntu/lab/scripts/path_truth.py /tmp/cs30401-controls/delay26/state dynamic_state_100ms_for_200s 1584 1585 /work/path_truth_delay26.csv
docker exec kim-study-replay python3 /work/replay_cases.py --workers 3
docker exec kim-study-replay python3 /work/analyze_replay.py
docker exec kim-study-replay python3 /work/analyze_phase2.py
docker exec kim-study-replay python3 /work/compare_replay.py --out /work/reproduction_v6.json
docker exec kim-study-replay python3 /work/export_evidence.py --execution-record /work/replay_execution.json --out /work/evidence-replayed
docker exec kim-study-replay python3 /work/extract_event26.py --output /work/event26_replayed.csv
```

`replay_cases.py` reads all 75 committed case manifests and uses the installed canonical patch; `analyze_replay.py` preserves the published event definitions and analysis parameters. `analyze_phase2.py` then regenerates `phase2_results.json` and `phase2_results.csv` for the 52 phase-two cases, using the committed question definitions in `phase2_execution.json`. It writes those result files in place and verifies complete finite delivery before reporting completion time. Finite-flow completion is measured from the zero-time application start to final unique sink delivery and includes connection establishment. Bulk transfers have no completion-time claim.

`compare_replay.py` checks full raw input and full analysis hashes against published records. `export_evidence.py` regenerates a combined table as `evidence-replayed/results.csv`, keeping newly measured runtime/patch provenance separate from published evidence; it refuses an existing output directory. `extract_event26.py` regenerates and validates the first LEO packet/ACK evidence excerpt. These commands map the tables and event timestamps to executable code; metadata such as measured wall time and patch version can differ from historical executions while measured behavior is compared explicitly.

A subset can be selected, for example `python3 /work/replay_cases.py leo10-base leo10-guard20 --workers 1`; analyze it normally, but the full comparison/table/event commands require their referenced cases to exist. The routing-timing control requires `make_state_control.py` first; all other LEO runs use the unmodified official Seoul–London state.

The original 20-case matrix took **278.014 seconds wall time**, with at most three concurrent simulations on Docker allocated 12 CPUs and approximately 8.15 GB RAM. Individual measured times are in manifests. Build, environment check, analysis and rendering are additional. This is a hardware-specific measurement, not a runtime guarantee. Deterministic configurations are not independent statistical replicates.

The phase-two 46-case batch took 86.168 seconds and its six added controls 0.251 seconds. The recorded **86.419-second sum** excludes time between batches; it is not a continuous 52-case execution measurement. The 75-case fresh-volume simulation replay took **377.093 seconds**, excluding its build, analysis, comparison and rendering. Its raw-input and full-analysis hash comparison passed for all recorded cases.

The canonical [ns3.patch](ns3.patch), version 6, has SHA-256 `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`; [ns3-v6.patch](ns3-v6.patch) preserves the same artifact. It adds an optional known-size exemption and targeted sequence-loss controls. Empty study parameters retain baseline threshold 3.

Historical provenance is preserved: the initial 20-case matrix used [study-v4.patch](study-v4.patch), SHA-256 `b4189c7689379a523decf564605b055e836981f948d8ca6e662cbe81dd8fbf99`; [study-v5.patch](study-v5.patch), SHA-256 `b5657a3b2919ed32ea7fcb8f14a922a75a94cc4d9910e99f809c771747cff3e6`, added the microbenchmark's finite `max_bytes` argument while retaining the 100-GB default. The original final three cases used v5. Apply **one patch only** to a clean source tree. For a historical replay, select the corresponding case names and pass `--patch` with that patch after applying it in a separate clean volume; phase-two controls require v6. Patch selection records provenance and does not apply or verify the installed patch for you.

For a **phase-two-only** rerun, prepare another empty container/volume with the v6 patch and path truth, then replace the full replay commands with:

```powershell
docker exec kim-study-replay python3 /work/run_phase2.py --workers 3 --patch /work/ns3.patch --execution-out /work/phase2_execution_replayed.json
docker exec kim-study-replay python3 /work/analyze_phase2.py
```

`run_phase2.py` generates all 52 defined cases. Its separate output records the new execution; the analyzer uses the committed definitions for the same cases and regenerates the two result files. These commands are an alternative to the 75-case replay, not a second run in an existing case directory. A subset can be run by naming its cases, but the phase-two table analyzer expects all 52 cases to exist.

## Render publication figures

Only plotting needs external Python packages. The locked dependencies are Matplotlib 3.10.8 and NumPy 2.4.4; simulation orchestration and analysis use Python's standard library. After replay and analysis:

```powershell
docker exec -w /work kim-study-replay uv sync --frozen
docker exec -w /work kim-study-replay uv run --frozen python /work/plot_study.py --drop-layer PhyRxDrop --stage 'replayed initial cases, canonical v6' --out /work/figures/replayed
docker exec -w /work kim-study-replay uv run --frozen python /work/plot_study.py --only loss --loss micro-tail-base-v5 micro-tail-guard20-v5 --drop-layer PhyRxDrop --loss-completion-bytes 27600 --loss-title 'Short-flow actual-loss counterexample' --stage 'replayed initial short-flow controls, canonical v6' --out /work/figures/replayed-tail
docker exec -w /work kim-study-replay uv run --frozen python /work/plot_phase2.py --results /work/phase2_results.json --runs-root /tmp/cs30401-study --out /work/figures/replayed-phase2
```

`plot_study.py` produces `route_event_causal` for the declared 26.2-second episode, `receiver_goodput_comparison` for full-run versus event-window effects, `stable_path_loss_recovery` for injected physical receive loss, and `candidate_baseline_traces` for the CUBIC/Vegas/BBR probes. The separate short-flow command adds completion of all 27,600 application bytes.

The `plot_phase2.py` command produces four PNG/PDF pairs and `figure_sources.json`:

| Figure | Cases and claim |
| --- | --- |
| `finite_size_first_loss` | First-loss size sweep, including 21-MSS cutoff and 22-MSS failure. |
| `finite20_loss_position` | First/middle/last loss in the 20-MSS transfer; final-segment timeout remains. |
| `protection_window_offset` | Whole-run and fixed true-event delivery versus shifted oracle windows. |
| `finite_delay_step` | Six matched 80-MSS stable/delay-step cases; the benefit is synthetic-control completion time. The separate 20-MSS sanity controls remain in the results table. |

For the sole measured K8 point, add `--include-k8` and choose another output directory; this does not imply a K8 size sweep. After a phase-two-only run, render only `plot_phase2.py`, because the initial 23 runs required by `plot_study.py` are absent. Axes and labels distinguish measured SRTT, unique receiver delivery and cwnd. No statistical confidence intervals are supplied.

## Source changes and limits

The patch adds opt-in transmission identity, receiver delivery/state/drop traces and a two-node control benchmark. In detailed flow logging mode, `CS30401_STUDY_TRACE=1` enables the new traces. Existing legacy traces were byte-identical with instrumentation disabled/enabled in the checked pilot. The experimental controller uses schedule `AdditionalParameters`, for example:

```text
study_threshold=20;study_windows=26100000000:26500000000|74900000000:75300000000
```

Thresholds affect both duplicate-ACK handling and SACK packet-count presumed-loss marking. A larger threshold does not clear already marked losses. Restoration is deferred until a permitted final congestion state; the effective protection may exceed its requested interval. Actual durations and deadline misses are reported. Notifications in these experiments are oracle information; a deployable notification path, its error and cost have not been implemented.

Version 6 optionally adds `study_short_flow_cutoff_pkts=21`. Before connecting, the sender computes `ceil(MaxBytes / SegmentSize)` for a known nonzero `MaxBytes`; at **21 or fewer nominal MSS equivalents**, it retains threshold 3 for the entire flow. Larger or unknown-size streams are not exempted. This is an upfront transfer-size policy, not an adaptive flight-size or remaining-ACK rule. It requires application-size knowledge; it does not eliminate final-segment timeouts or the measured 22-MSS failure. Cutoff 21 is exploratory, not a proved optimum.

Generic analyzer fields such as `protection_intervals` and `restore_deferrals` describe controller lifecycle events. They can include `THRESHOLD_SET` changes from 3 to 3 in exempt flows, so their presence or count does not prove that a high threshold was active or caused a delay. Check raw `THRESHOLD_SET` rows with `new_value > 3` together with `SHORT_FLOW_GUARD_BYPASS` before interpreting effective protection. Conversely, a socket can close before the scheduled end, leaving no completed interval despite a recorded high-threshold activation. Published raw metrics are preserved; this distinction changes their interpretation.

The phase-two offset cases shift both ends of the 26.2/75.0-second protection windows. They do not simulate notification transport delay, clock drift or a stochastic prediction error. Their successful tested offsets cannot be stated as a universal accuracy interval. Positive finite-flow step results likewise cannot be reported as the whole-run LEO benefit.

`make_state_control.py` creates symlinks under `/tmp/cs30401-controls` and replaces only its own forwarding-file links at 26.2–26.8 seconds with the 26.1-second snapshot. It does not edit the official state or freeze satellite movement. `path_truth_*.csv` are small derived path diagnostics, not generated constellation state directories.

ns-3.48's tested CUBIC/SACK/PRR implementation lacks RACK-TLP. Observed receiver wire arrival alone is not proof of application acceptance; the analyzer requires positive acceptance evidence. Hook coverage is checked, including `TrafficControlLayer::Drop` before device queue admission and root queue-disc absence. This does not audit every possible receiver TCP rejection path. Every conclusion must retain the stack and scenario scope described in the note.

Reordering protection is existing prior art. The references in the experiment note distinguish earlier mechanisms from the proposed selective activation study. The code uses the official course/Hypatia environment and ns-3 APIs, with GPT-assisted modifications; neither code nor measurements should be described as an independently invented TCP stack.

## Final report and submission constraints

The [Team 5 draft PDF](report/kim-study-draft.pdf) and [LaTeX source](report/kim-study-draft.tex) are for review. The source uses the unchanged official `IEEEtran` conference class. The three members' verified English names are still missing, so the author line and submission identity remain incomplete. The draft is not a submission-ready ZIP.

The draft has compiled successfully and all six PDF pages have been visually checked: five pages of main text and one page of references. This satisfies the report's page limit for this independent study; final team scope and author identity still require review. The archived [fresh replay case records](evidence/replay_case_manifests_v6.json) and [regenerated figure source records](evidence/figure_replay_sources_v6.json) connect the report to the measured cases and figure inputs.

Optional report compilation requires TeX; the course image does not include it by default. The checked build used TeX Live 2023 / pdfTeX 1.40.25 and IEEEtran 1.8b. In the replay container, install the standard packages and run two passes from the report directory:

```powershell
docker exec -u 0 kim-study-replay apt-get update
docker exec -u 0 kim-study-replay apt-get install -y --no-install-recommends texlive-latex-base texlive-latex-recommended texlive-publishers texlive-fonts-recommended
docker exec -w /work/report kim-study-replay pdflatex -interaction=nonstopmode -halt-on-error kim-study-draft.tex
docker exec -w /work/report kim-study-replay pdflatex -interaction=nonstopmode -halt-on-error kim-study-draft.tex
```

After the current draft PDF is in place, create a review package with Python's standard library in the replay container, then copy it into the Windows output directory. This does not require a host Python installation, TeX or plotting dependencies:

```powershell
docker exec kim-study-replay python3 /work/build_submission.py --out /tmp/Lab1_5_draft.zip
New-Item -ItemType Directory -Force .\output | Out-Null
docker cp kim-study-replay:/tmp/Lab1_5_draft.zip .\output\Lab1_5_draft.zip
```

Without `--out`, the builder defaults to `/work/Lab1_5_draft.zip`, visible as `code/kim-study/Lab1_5_draft.zip` on the host. The builder includes top-level `report.pdf`, `README.md` and the selected `code/kim-study/` files; it checks the expected file count, ZIP integrity and forbidden paths before publishing the archive. State, raw traces and excerpts, runtime replay outputs, ns-3 source/builds and virtual environments are excluded. Packaged Markdown explains how to regenerate the excluded packet excerpt. The output remains a **DRAFT** until author identity, final team scope and submission checks are complete.

The English report must use the unchanged IEEE conference two-column, 10-point Times template, Team ID and all names under the title, and the six requested sections: Introduction, Problem Statement, Proposed Idea(s), Experiment Setup, Evaluation, Conclusion. It is limited to six pages excluding references/appendix. For this study, lead with one validated mechanism and use related subquestions to establish the benefit/cost boundary; multiple unrelated weak claims would consume that space without stronger evidence.

Problem, idea, soundness, reproducibility, clarity and presentation are the six stated grading dimensions; the handout assigns no numeric weights. A small measured gain can be defensible when the TCP mechanism, baseline, information assumptions, counterexamples and reproducibility are convincing. Current incomplete candidates must remain hypotheses.

The final `Lab1_{TeamID}.zip` must contain `report.pdf`, `README.md`, `code/`, reproducible commands/runtime/figure mapping, and `pyproject.toml` plus `uv.lock` for Python dependencies. Generate the final patch using the official `make_patch.sh`, for example `docker exec kim-study-replay bash /home/ubuntu/lab/scripts/make_patch.sh /work/ns3.patch`. Exclude state, raw traces, raw trace excerpts, the ns-3 source tree and builds; regenerate review excerpts with the included script. This folder is an experiment bundle. The Team 5 study draft has been compiled and rendered; its measured code and report meet the technical and format checks described here within the tested study scope. The three members' verified English names, final common scope, final submission review, individual surveys and presentation remain incomplete. Further paths or multi-flow experiments strengthen scope but are not a fixed test-count requirement in the handout.
