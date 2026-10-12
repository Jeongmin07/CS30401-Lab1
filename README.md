# CS30401 Lab 1 — Team 5

This repository holds the team's shared lab work. Use the map below to find a result without reading every study file.

## Current direction under review — 12 October 2026

Read [the current results and research retrospective](docs/research/20261012-progress-retrospective.md) for the interpretation of the completed studies, throughput headroom in the representative setup, and the assumptions behind proactive CUBIC window changes and selective loss waiting. It distinguishes measured effects from unimplemented candidates and links the source audit. It proposes priorities for review without deciding the team's final topic.

The latest work completed **21 valid simulations across four independent candidates in parallel**: orbit-derived BBR BDP targets, BBR ProbeRTT timing, CUBIC HyStart, and short new-data holds. Start with [the common comparison and handoff](docs/experiments/20261012-parallel-candidates.md), then read each linked experiment and replay README. Each track uses a separate source volume. One additional BBR attempt used an outdated runtime during a build and is retained separately, excluded from performance results. [Draft PR #16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16) holds the unmerged evidence; these experiments do not decide the team's final topic.

There is no clear large performance gain in these settings. BDP targets and holds did not improve LEO throughput; disabling HyStart was worse, and the fixed-window HyStart candidate deferred no actual exit. Early BBR remeasurement moved a service dip and produced a small net difference with added drop records. The common record shows each matched pair and its costs; these different scenarios are not an algorithm ranking.

The earlier [13-case loss-tolerance study](docs/experiments/20261012-forecast-loss.md) is preserved separately. It found small whole-run gains and remaining true-loss completion costs, not a large throughput improvement. Elevation-based capacity control and bandwidth-only BBR route convergence are excluded from the four new tracks. The supplied state contains only Seoul and London, uses constant link rates, and the provided loss-recovery stack lacks modern Linux RACK-TLP. Existing Vegas results remain available but are not the central candidate. Earlier BBR diagnostics are preserved in [the diagnostic tools](code/bbr-route/README.md).

## What is here?

| Location | What you will find | Start with |
| --- | --- | --- |
| [`docs/`](docs/) | Course handout and environment guide, team workflow, and experiment records | [`docs/START_HERE.md`](docs/START_HERE.md) for collaboration; [`docs/LAB_REFERENCE.md`](docs/LAB_REFERENCE.md) for the assignment |
| [`code/kim-study/`](code/kim-study/) | Seongchan's **independent** CUBIC/SACK/PRR investigation: patch, scripts, compact evidence, figures, and report draft | [`code/kim-study/README.md`](code/kim-study/README.md) for the question, main findings, limits, and replay commands |
| [`docs/experiments/20261010-cubic-q75.md`](docs/experiments/20261010-cubic-q75.md) | A separate six-run check of the CUBIC queue-size result, including a new 75-packet condition | Read this experiment record, then its linked small data files |
| [`shared-results/`](shared-results/) | Eight 200-second, 100-Mbit/s exploratory runs (BBR, CUBIC, NewReno, Vegas at two queue sizes) and an earlier 20-second check | Compare each run's configuration and flow summary. The newer BBR/Vegas folders contain summaries only; detailed traces are not in Git. These are **different settings** from the 10-Mbit/s CUBIC study |

The 10-Mbit/s study is research evidence, **not a team-approved final topic or submission**. Agreed decisions belong in [`docs/PLAN.md`](docs/PLAN.md). The older 100-Mbit/s `shared-results/` runs are not inputs to Seongchan's study or the new 75-packet check. Compare runs only after checking their rate, queue, duration, flow, TCP implementation, and patch.

## Which study files matter?

1. [`code/kim-study/EXPERIMENT_NOTE.md`](code/kim-study/EXPERIMENT_NOTE.md) explains the first 23 recorded cases. [`PHASE2_NOTE.md`](code/kim-study/PHASE2_NOTE.md) explains the 52 follow-up cases and the limits of the short-flow exemption.
2. [`code/kim-study/evidence/results.csv`](code/kim-study/evidence/results.csv) and [`code/kim-study/phase2_results.csv`](code/kim-study/phase2_results.csv) are compact result tables. The `evidence/cases/<case>/` folders hold exact settings and compact summaries. Large packet traces stay outside Git and can be regenerated.
3. [`code/kim-study/ns3.patch`](code/kim-study/ns3.patch) is the **canonical version-6 patch** for a fresh ns-3 source tree. `ns3-v6.patch` is the same preserved artifact; `study-v4.patch` and `study-v5.patch` document earlier versions. Apply **one** patch to a clean volume. The various `reproduction*.json` files document different historical replay checks; use `evidence/reproduction_v6.json` for the complete 75-case check.
4. [`code/kim-study/report/kim-study-draft.pdf`](code/kim-study/report/kim-study-draft.pdf) is a review draft. It lacks confirmed team author names and is not ready to submit.

## Where do new files go?

| Kind | Location |
| --- | --- |
| One experiment's question, commands, results, and limits | `docs/experiments/<date>-<topic>.md` |
| Its small CSV/JSON evidence and exact run settings | `docs/experiments/assets/<date-or-topic>/` |
| Reusable simulation/analysis code and ns-3 patches | `code/` |
| Current work handoff | `docs/work/<github-login>.md` |
| Team-approved plan | `docs/PLAN.md` |
| Large raw traces, generated state, and temporary runs | Local Docker/container storage or an agreed shared archive; record where and how to regenerate them |

The repository root's `runs/` directory, if present on your computer, is a **local output folder ignored by Git**. It is not automatically uploaded or visible to teammates. GitHub shows only committed and pushed files. Existing tracked files under `shared-results/` remain available for historical context.

## Work together

Read [`docs/TEAM_WORKFLOW.md`](docs/TEAM_WORKFLOW.md) and check [open pull requests, including drafts](https://github.com/Jeongmin07/CS30401-Lab1/pulls) before editing another person's work. Use a task branch for new evidence; merge into `main` after a teammate reviews it. The course environment is `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1` (ns-3.48 with the supplied Hypatia modules). Final submission materials must be in English.
