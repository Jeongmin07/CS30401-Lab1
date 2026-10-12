# Route-shortening CUBIC diagnostic

This track first tests the premise for proactive cwnd drain or pacing: a natural supplied route shortening must be associated with a concrete, attributable queue/drop surge, rather than only reordered packets or a smaller propagation BDP.

Read the [predeclared diagnostic and final decision](../../docs/experiments/20261012-orbit-cubic-down.md). The candidate was screened out before implementation: completed event windows show queue changes but no actual drop, and the shared 100-Mbit/s q100 attempt timed out within its 240-second budget. No duplicate baseline, active controller, ON run, or new topology was launched here. The faster small-queue condition is unverified, not reported as drop-free.

`analyze_gate.py` is a stdlib, posthoc extractor of exact application bytes, sender/recovery events, tagged drops and per-device queue visits in the declared windows around supplied shortening events. It never labels an RTT fall as overflow and refuses failed/incomplete manifests or existing outputs.

```text
python3 -B /work/code/orbit-cubic-down/analyze_gate.py --run /tmp/orbit-cubic-up/cubic10-observed200 --path-truth /work/code/kim-study/path_truth_200s.csv --out /tmp/cubic-down-gate-replayed.json
```

Use the owning `orbit-cubic-up` shared raw/source record for simulation replay; this track adds no ns-3 patch. The report distinguishes per-queue served visits from end-to-end delay, actual flush-time occupancy from bin-boundary snapshots, and completed conditions from preserved timeout artifacts.
