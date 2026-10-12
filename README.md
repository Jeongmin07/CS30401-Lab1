# CS30401 Lab 1 — Team 5

This repository holds the team's shared lab work. Use the map below to find a result without reading every study file.

## Current direction under review — 13 October 2026

Start with [the queue follow-up](docs/experiments/20261013-queue-mitigation.md). Eleven fixed conditions are complete. For the supplied single flow at fixed 10 Mbps over 200 s, native pacing with a predetermined payload ceiling based on the operator's known capacity preserves goodput (9.546509→9.566270 Mbps), reduces source mean queued packets in 75–75.5 s from 87.23 to 0, and removes observed tagged data losses (486→0 over 200 s). Whole network queue packet-time falls 91.947%; source zero waiting is confirmed across 436 actual served visits in that window, while downstream queueing remains. [Pacing code/replay](code/queue-pacing/README.md) and [full results](docs/experiments/20261013-queue-pacing.md) preserve settings and costs.

This remains an **opt-in bulk setting with known capacity**. Native pacing without that ceiling loses 5.13% goodput; FIFO moves the same backlog; default CoDel reduces delay but loses 6.35% goodput ([queue controls](docs/experiments/20261013-queue-backpressure.md)). A real startup loss has the same first retransmission latency and a 0.10% goodput decrease with the selected setting. The 27.6 KB actual-loss flow with a false hint worsens from 0.257224 to 0.471435 s because the native sender rate becomes 2.208 Mbps, so global enablement and short-flow safety are unsupported. Two remaining natural retransmissions repeat data already delivered to the app. This comparison does not establish the separate effect of stock TCP plus capacity pacing, competition safety, or general LEO behavior.

The previous [last-packet and queue follow-up](docs/experiments/20261013-tail-and-queue.md) is preserved. Ten fixed tail conditions are complete. In the27.6KB actual-loss flow with a deliberately wrong route hint, one extra final original segment reduced completion time from0.350482 to0.257224 seconds, still above baseline0.251510 seconds. The admission uses at most one MSS beyond the ordinary flight allowance and preserves the shared loss deadline. It does not act in the21MSS boundary or ongoing100GB LEO bulk conditions, so it adds no bulk throughput improvement. Read [the detailed experiment](docs/experiments/20261013-orbit-tail.md) and [standalone replay](code/orbit-tail/README.md).

The independent [paired queue audit](docs/experiments/20261013-orbit-queue.md) reproduces the prior trajectories exactly. Selective waiting already has a larger source queue before T75. Its eleven later discards occur at the full 100-packet source GSL queue with device-stop set, no BQL and no root qdisc. Baseline reaches the same stopped-device discard mechanism at T77. The predeclared two-direction routing-delay counterfactual preserves the pre-T75 history and moves the switch to T78: eleven drops, twelve retransmissions and two recoveries remain around T75, with the first drop 53.305 ms later. Thus the T75 switch is not necessary for this overflow under the fixed policy, although it affects timing. These diagnostics do not establish physical handover feasibility or select the team's final topic. All thirteen new conditions completed; raw evidence and verification are linked in the common record.

The earlier [three bounded follow-ups](docs/experiments/20261012-three-followups.md) are preserved. Proactive CUBIC window expansion and draining stopped at diagnostic gates: the observed source link stayed busy during the largest natural RTT increase, and shortening-window buffer drops were not established. A separate 100-Mbit/s passive attempt hit its 240-second wall cap and remains unverified. Neither gate ran an active policy.

Selective old-flight loss waiting keeps K3 and shares one short deadline across eligible presumed-loss holes. In seven final controls, natural LEO goodput was 9.544356→9.5465088 Mbit/s, matching the earlier bounded K20 result. The first window's retransmissions/recoveries fell from 3/1 to 0/0; a later window had 12/2 versus baseline 0/0. A tagged genuine loss in the supplied LEO simulation path added 5.736 ms before retransmission. The false-positive-hint, 20MSS genuine-loss micro increased completion time from 0.251510 to 0.350482 seconds. This retains a small measured benefit and a material finite-flow cost. Read [the experiment](docs/experiments/20261012-orbit-loss.md) and [replay instructions](code/orbit-loss/README.md). New raw evidence is in [the follow-up prerelease](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/orbit-followups-20261012).

Read [the current results and research retrospective](docs/research/20261012-progress-retrospective.md) for the interpretation of the completed studies, throughput headroom in the representative setup, and the assumptions behind proactive CUBIC window changes and selective loss waiting. It distinguishes measured effects from unimplemented candidates and links the source audit. It proposes priorities for review without deciding the team's final topic.

The earlier work completed **21 valid simulations across four independent candidates in parallel**: orbit-derived BBR BDP targets, BBR ProbeRTT timing, CUBIC HyStart, and short new-data holds. Start with [the common comparison and handoff](docs/experiments/20261012-parallel-candidates.md), then read each linked experiment and replay README. Each track uses a separate source volume. One additional BBR attempt used an outdated runtime during a build and is retained separately, excluded from performance results. [Draft PR #16](https://github.com/Jeongmin07/CS30401-Lab1/pull/16) holds the unmerged evidence; these experiments do not decide the team's final topic.

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
