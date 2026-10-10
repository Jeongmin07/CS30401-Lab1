# Jeongmin07 — current handoff

**Branch:** `experiment/cubic-q75-followup`, based on merged `main` commit `b60e8e0`. **PR:** [#10](https://github.com/Jeongmin07/CS30401-Lab1/pull/10). The user authorized all experiments in the follow-up and publication. This extends Seongchan's independent CUBIC study with his canonical version-6 patch.

## Completed on 2026-10-10

- Located the original 474,720-byte queue-75 deficit: the protected run is ahead at 120 s, falls mainly over 120–130 s, and loses further delivery over 160–170 s. Exported receiver timelines, drops/congestion events, window checkpoints and original-packet acceptance evidence around 121.6 s.
- Ran 29 new configurations: later-event protection, smaller thresholds, changed queue/flow start, actual first-segment loss and a synthetic reordering control.
- Rebuilt the patch in a fresh Docker volume and replayed those 29 plus the two original comparison cases. All 279 raw-file SHA-256 hashes and 31 full-analysis hashes match.
- Shared compact settings/results, figures, reusable scripts and a compressed raw archive. Start with [the experiment explanation](../experiments/20261010-cubic-followup.md); it links the artifacts and has PowerShell commands.

## Findings and judgment

Threshold 8 around 26.2 s and 121.6 s removes the studied event recoveries and matches threshold 20's LEO delivery at queue 75, queue 50 and a one-second start shift. Gains are small: +0.0029%, +0.0764% and +0.1185%, respectively. Its 22-MSS real-loss penalty is 0.114720 ms versus threshold 20's 100.119680 ms. Threshold 8 does not improve the synthetic 80-MSS reordering case.

This supports a conditional mechanism/tradeoff study, with known event times. It is insufficient for a general throughput or deployment claim. The later-only setting has higher total delivery at queue 75 but retains the first mistaken recovery and increases later event-window recovery counts. Goodput and removing unnecessary recovery are separate objectives.

## Locations

- Scripts: `code/cubic-followup/`.
- Compact evidence: `docs/experiments/assets/cubic-followup-20261010/`.
- Shared raw archive: [experiment release](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/cubic-followup-20261010), SHA-256 in the experiment note.
- Local first-run traces: `lab1-codex-study-20261010:/tmp/cs30401-study/<case>/`.
- Fresh replay: `lab1-cubic-followup-verify-20261010:/tmp/cs30401-study/<case>/`.
- Previous six-case check: [queue-75 record](../experiments/20261010-cubic-q75.md), merged in PR #9.

## Remaining work

Evaluate the candidate on a held-out path or traffic mix, then inaccurate route-notification times. No event detector, RACK-TLP comparison, wireless-loss model or universal threshold has been validated. The canonical patch and common plan are unchanged. PR #10 is ready for review; it has not been merged into `main`.
