# K8 versus K20 under CUBIC competition

**Status: declared, running.** kim-seongchan with AI assistance, 2026-10-10; continuation of PR #12. This is an independent candidate evaluation, not a team-approved parameter choice.

## Question and fixed comparisons

Does K8 reduce genuine-loss recovery cost without worsening delivered-byte allocation when two CUBIC flows share the route? PR #10's single-flow K8 result does not answer coexistence. Reuse the original eight DD/K20 controls in [the comparison](20261010-cubic-competing.md), pinned to PR #12 head **aa4d4778a95daf310db0a4fb90c6453dec226310**. Preserve their raw data and summaries.

Add exactly six primary conditions: `same-start-gd-k8`, `same-start-dg-k8`, `same-start-gg-k8`, `join10-gd-k8`, `join10-dg-k8`, `join10-gg-k8`. Mode letters still identify flow 0/1. Both starts are 0 for same-start; flow 1 starts at 10 seconds for join10. Every G socket uses `study_threshold=8;study_windows=26100000000:26500000000|74900000000:75300000000`; every D socket retains K3.

Retain the 200-second supplied Seoul–London state, endpoints 1584→1585, 10-Mbit/s ISL/GSL links, 100-packet device queues, 100-GB transfers, CUBIC/SACK/PRR, seed 123456789 and no pacing. Canonical v6 patch, compiled binary and runner stay unchanged. These are PR #12's **26.1–26.5 and 74.9–75.3-second** windows; PR #10's new 121.5–121.9-second target is not imported. The known-size ≤21-MSS exemption does not activate for these bulk flows.

## Declared measurement and validation

- Compare individual app delivery, sum and Jain over common-active intervals: 0–200 or 10–200 seconds. Retain whole run, 20–200-second slice and the two original event windows separately.
- Keep per-flow data retransmissions, recovery/LOSS entries, dropped transmissions, sender SRTT, wire/app byte difference and actual guard/restoration times. Jain alone does not identify whether each competitor benefits.
- Validate two receiver connections, app/bin/count agreement with the unchanged analyzer, initial K3 and each intended K8 activation. Recheck canonical patch/binary/runner identity. A representative K8 case will be replayed on another fresh official volume.
- Audit the simultaneous GD first genuine-loss episode against DD using transmission tags and ordered delivery. A local delay does not explain every later sharing interaction.
- Store small settings/results and source/trace hashes in Git; archive the six raw bundles outside Git with a manifest. These are deterministic controls, not independent statistical repetitions.

No K8 result is claimed yet. After evaluation, add the measured results, limitations, reproduction commands and a proposed English report outline. No merge or final topic decision is included.
