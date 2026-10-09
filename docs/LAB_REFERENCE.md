# CS30401 Lab 1 Requirements and Repository Context

Lab 1 asks Team 5 to reproduce a specific TCP performance problem in a LEO satellite network, explain its mechanism, propose an improvement, and evaluate it against the same scenario without the improvement. The repository currently contains exploratory runs and collaboration documentation; the team has not selected a final problem or solution.

## Course sources

- [Lab handout](CS30401_26F_Lab1_Handout.pdf), 9 pages: task, evaluation, submission rules, and academic integrity.
- [Environment guide](CS30401_26F_Lab1_Environment_Guide.pdf), 15 pages: simulation model, installation, tools, configuration, and patch workflow.

The course documents define assignment requirements. This reference summarizes them and separately records repository observations. Example commands and example results in the guide are workflow demonstrations, not our research design or our measured results. Refer to the original PDFs when checking a requirement.

## Required research steps

1. **Problem statement:** reproduce one or more precise problems in simulation. Identify the TCP mechanism, triggering conditions, magnitude of degradation, and cause. Justify the relevance of the selected TCP implementation and the basis of every chosen parameter. If the model is extended, justify the duration, frequency, and strength of the new behavior and exclude artifacts caused by its implementation.
2. **Idea proposal:** explain how the idea addresses that cause. State assumptions, information requirements, a realistic way to obtain the information, necessary accuracy, deployment location, and deployment cost.
3. **Experiment and evaluation:** use the provided environment and report its version. Select relevant metrics, compare quantitatively against the unchanged baseline scenario, and evaluate useful conditions, unsuccessful conditions, costs, and limitations.

## Simulation model and limits

- Official image: `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1`, containing ns-3.48 and the course Hypatia modules.
- The path is ground station -> satellite -> ISLs -> satellite -> ground station, without gateways or terrestrial segments.
- Default constellation: Starlink shell 1, 72 planes x 22 satellites = 1,584 satellites; 550 km altitude, 53-degree inclination, 25-degree minimum elevation, and four +Grid ISLs per satellite.
- The provided Seoul-London state spans 200 seconds. Forwarding routes are precomputed by distance at 100 ms intervals and loaded by ns-3 at the corresponding simulation times. Propagation delay follows node distances.
- Satellite switches occur instantly. The default model has no link-layer handover outage, random bit errors, or time-varying link capacity. Packet loss occurs through device queue overflow or lack of satellite visibility. Each device has a drop-tail queue without a queueing discipline.
- TCP settings applied by Hypatia include an initial congestion window of 10 segments, 1,380-byte segments, 32 MiB send and receive buffers, SACK, timestamps, and window scaling. Remaining settings follow ns-3.48 defaults.
- Link rates, queues, stations, traffic, TCP implementations, and code can be changed with a stated basis. A run cannot exceed its state duration. The guide's 20-second, 100 Mbit/s CUBIC example with a 1,000-packet queue is an environment check, not a required research condition.

Useful tools are `check_env.sh`, `gen_state.py`, `make_run.sh`, `run_sim.sh`, `path_truth.py`, `viz_path.py`, and `make_patch.sh`. TCP logs contain congestion-window changes, smoothed RTT changes, acknowledged-byte progress, and per-flow summaries. Their event timestamps must be used when aligning traces; rows need not be evenly spaced.

## Submission and dates

- Team deadline: **2026-10-13 at 23:59 KST**, submitted by one member on KLMS as `Lab1_{TeamID}.zip`.
- Each member separately submits the mandatory Contribution Survey by the same deadline.
- Presentation: **2026-10-15**, at most 10 minutes per team, with every member presenting part of the work.
- All final submitted materials must be in English.

The team archive contains `report.pdf`, `README.md`, and `code/`. The report uses the unchanged IEEE conference template: two columns and 10-point Times. Put the Team ID and all member names under the title. Sections 1-6 have a six-page limit; references and appendices are excluded from that limit. Figures need legible labels and units.

Report sections: Introduction; Problem Statement; Proposed Ideas; Experiment Setup with parameter bases; Evaluation; Conclusion; References; optional Appendix.

`code/` must reproduce every reported result: scenario and experiment scripts, configurations or generators, implementation, analysis and plotting scripts, and the exact custom-state generation command if applicable. Submit ns-3 changes as a patch made with `make_patch.sh`. Exclude constellation state files, simulation logs, the ns-3 source tree, and build artifacts from the final course archive. External Python dependencies require `pyproject.toml` and `uv.lock` managed with `uv`; standard-library-only scripts need no dependency files.

The submission README must state patch/build steps, exact experiment commands and approximate runtimes, and a command mapping for every reported figure and table. The TA will reproduce results in the stated course environment with a fresh ns-3 volume. A single `run_all.sh` is recommended. Verify the final archive in a clean environment before submission.

AI tools are allowed. Submitted numbers must match code outputs, references must exist and support the claims, related work including Hypatia must be cited, and reused course/ns-3 code must be acknowledged in the README.

## Repository observations on 2026 10 09

Read baseline: `main` at `59e4f4f7f34aa71113c8a570a749ba0e3e0f7875`, verified in the local clone and remote refs. [PR #2](https://github.com/Jeongmin07/CS30401-Lab1/pull/2) has been merged. Before this reference upload, authenticated GitHub API queries showed zero open Issues and zero open PRs, including drafts. The remaining `docs/team-ai-workflow` branch is the collaboration-documentation branch. Some existing plan/work notes still describe PR #2 as awaiting review; its live GitHub status is newer than that wording.

Three students work on separate laptops with separate AI conversations. Pushed files, Issues, PRs, and experiment records supply shared context. Chats, local changes, running experiments, and Docker volumes are not shared automatically. See [team context](START_HERE.md), [team workflow](TEAM_WORKFLOW.md), [common plan](PLAN.md), and [existing kim-seongchan handoff](work/kim-seongchan.md).

The existing results were added at `fa99ffa6772b1d4d6826b557ad49b74b5b28eb61`. The following values were read from the existing `config_ns3.properties`, `tcp_flows.txt`, and `timing_results.txt` files. They were **not rerun** for this reference.

| Existing run | TCP | ISL and GSL queue in packets | Logged average rate in Mbit/s | Logged simulation execution time in seconds |
| --- | --- | --- | --- | --- |
| [cubic/q1000_200s](../shared-results/runs/cubic/q1000_200s/) | CUBIC | 1,000 | 95.9 | 1,614.7 |
| [cubic/q100_200s](../shared-results/runs/cubic/q100_200s/) | CUBIC | 100 | 81.5 | 1,173.6 |
| [newreno/q1000_200s](../shared-results/runs/newreno/q1000_200s/) | NewReno | 1,000 | 70.8 | 1,327.7 |

All three configurations specify a 200-second Seoul-London simulation, 100 Mbit/s ISL/GSL links, 100 ms routing updates, seed `123456789`, pacing disabled, and flow 0 logging. The flow summaries show sender 1584, receiver 1585, and an ongoing bulk flow when the simulation ends. The execution times are the logged `Run simulation` stage, including event/logging work, not simulated duration or isolated CPU time. An earlier 20-second check is also present under `shared-results/runs/r1/`.

These rates are observations, not evidence of why the difference occurs. They do not establish a route-change failure, a handover outage, or a validated TCP fix. The exact execution-time code/patch, hardware, and independent reproduction still need to be recorded or checked before treating these runs as final evaluation evidence.

## Work still to agree and complete

The common plan leaves the TCP problem, improvement, member assignments, research parameter bases, common analysis method, and final patch/merge owners undecided. Shared analysis code and a research implementation have not been integrated into `main`. Existing setup files in `kim-seongchan/cs30401-2026f-lab1-team05` are a candidate for a separate setup PR.

A useful next sequence is to agree who integrates setup and who builds the common trace-analysis tool; align cwnd, smoothed RTT, acknowledged progress, and route-change times; distinguish queue effects from LEO-specific mechanisms using controlled comparisons; then agree on one supported problem and implement and evaluate its improvement. These are next-work candidates, not new team decisions.

For this upload, kim-seongchan's scope is source PDFs and this reference. No simulation, TCP modification, change to the team's common plan, or modification of another member's results is included. The user explicitly requested a direct commit and push to `main` for this reference upload, without a PR. For later work, follow the repository workflow with one branch and PR per coherent deliverable, explicit reproduction evidence, exported ns-3 patches, and review before a separately instructed merge into `main`.
