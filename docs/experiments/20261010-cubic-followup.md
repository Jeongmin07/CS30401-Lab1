# CUBIC follow-up: later congestion and protection costs

**Status:** in progress. Jeongmin07 requested this investigation and authorized Docker experiments and publication. Branch `experiment/cubic-q75-followup` starts at merged `main` commit `b60e8e0`. This extends the [75-packet check](20261010-cubic-q75.md) and uses Seongchan's canonical version-6 patch without modifying it.

## Question

Why does first-event protection at a 75-packet queue improve delivery around 26.2 seconds yet lower total 200-second delivery by 474,720 bytes? Can a smaller loss threshold or protection around a later route change improve the tradeoff, and what happens under changed traffic and real packet loss?

## Declared checks

1. Read the original receiver-delivery, drop, and congestion traces. Export one-second bins and exact interval totals using `code/cubic-followup/compare_traces.py`.
2. Compare threshold 4 with threshold 20 around 26.2 seconds, and test a separate protection window at 121.5–121.9 seconds. The latter surrounds the observed 121.6-second route transition. These times remain oracle inputs.
3. Repeat the candidate under a one-second flow-start shift and a 50-packet queue, each with its own unchanged baseline.
4. Measure completion time for genuine first-segment loss in 20- and 22-MSS transfers, plus the recorded synthetic 80-MSS reordering control. Record unsuccessful conditions as well as benefits.

All runs use the official image digest and canonical patch identified in the prior experiment. LEO runs retain Seoul–London, 200 seconds, 10 Mbit/s links, one bulk flow and 100-ms route updates. The new scripts record exact commands and never overwrite existing case directories. Raw traces remain in Docker; only small evidence and reproducible code will be committed.

## Preliminary trace observations

The existing first-window-only case is ahead by 95,220 delivered bytes at 120 seconds. It loses 603,060 bytes relative to baseline over 120–130 seconds and 367,080 over 160–170 seconds; delivery differences in other intervals partly offset those losses. A second recovery near the 121.6-second route change occurs in both runs, with a smaller congestion window in the previously protected run. This timing association motivates the later-window control; it is not yet a proof of the downstream mechanism.

Results, reproduction commands, source excerpts, and limitations will be added after the declared controls complete.
