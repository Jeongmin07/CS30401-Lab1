# CS30401 Lab 1 - Team 5

Shared repository: <https://github.com/Jeongmin07/CS30401-Lab1>.

We are three students working on the lab on separate laptops. Each student uses their own AI assistant. The assistants share information through this repository; they do not share a chat history, filesystem, Docker volume, or live view of another student's work.

## Start here

- **Students and new AI chats:** read [the team context](docs/START_HERE.md). Use your own wording when asking your assistant to work; there is no required starting prompt.
- **AI assistants:** read [AGENTS.md](AGENTS.md), then check the latest GitHub Issues and open PRs, including draft PRs.
- **Working together:** follow [the team workflow](docs/TEAM_WORKFLOW.md).
- **Agreed research direction and experiment settings:** see [the current plan](docs/PLAN.md).

Track tasks and questions in [Issues](https://github.com/Jeongmin07/CS30401-Lab1/issues). Share code and work in progress through [pull requests](https://github.com/Jeongmin07/CS30401-Lab1/pulls). One coherent deliverable uses one working branch and one PR; an assistant can stay on that branch through multiple conversations and experiments.

## Where to put shared records

| Location | Purpose |
| --- | --- |
| `docs/PLAN.md` | Decisions the students have agreed on |
| `docs/work/<github-login>.md` | Each student's latest progress and handoff, following the work template |
| `docs/experiments/issue-<number>-<run-id>.md` | Reproducible experiment evidence, following the experiment template |
| `docs/experiments/assets/` | Small plots or summary tables referenced by experiment records |
| `code/` | Reproducible experiment/analysis scripts and ns-3 patches, when added |

Templates: [work record](docs/templates/work.md), [experiment record](docs/templates/experiment.md). These are guides to useful information, not required prompt or response formats. Records on another branch are visible after that branch is pushed; read its draft PR and branch contents instead of assuming all progress is already on `main`.

## Environment and current state

The course environment is `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1`, containing ns-3.48 and the course Hypatia modules. Source: <https://github.com/Yeonjong21/cs30401-lab1-env>.

As of 2026-10-09, `main` includes [shared experiment outputs](https://github.com/Jeongmin07/CS30401-Lab1/tree/fa99ffa6772b1d4d6826b557ad49b74b5b28eb61/shared-results): 200-second CUBIC runs with queues of 1,000 and 100 packets, a 200-second NewReno run with a queue of 1,000 packets, and an earlier 20-second check. These are existing observations, not an agreed final research design. This PR adds collaboration documentation and GitHub templates. Shared analysis tools and a research implementation have not yet been integrated here. Existing setup files from <https://github.com/kim-seongchan/cs30401-2026f-lab1-team05> can be proposed in a separate setup PR.

Git tracks pushed files. Each laptop's ns-3 Docker volume must be shared through an exported patch. For future experiments, keep code, configurations, small summaries and plots in Git; archive large raw logs in an accessible shared location and link them from the experiment record. See [result sharing](docs/TEAM_WORKFLOW.md#실험-결과-공유). Existing uploaded results are preserved. A small plot or summary without its exact command, code revision and configuration is insufficient evidence for a research result.

Collaboration notes may be written in Korean. All materials included in the final course submission must be written in English.
