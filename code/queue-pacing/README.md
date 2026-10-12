# Native CUBIC pacing and an operator-capacity ceiling

Read the [fixed declaration](../../docs/experiments/20261013-queue-pacing.md). Initial controls are pacing OFF, native defaults ON, and native ON with a predetermined payload ceiling of 9623430 bps for the physical 10 Mbps/1380-byte payload/1434-byte serialized data packet. Current selective+tail policy remains identical; additional observers integrate exact queue state without changing native decisions. No simulations launch before the parent's source checkpoint.

All eight declared conditions are complete on one runtime. The capacity ceiling improves natural bulk goodput 9.5465088→9.5662704 Mbps, whole distinct drops 486→0 and all-device queue packet-time by 91.947%. Native-only misses the throughput floor. The selected micro true-loss FCT is 0.471434773 s versus current selective+tail 0.257223678 s: **83.28% slower**, with no extra tail admission. Treat this as an opt-in fixed-capacity long-bulk setting, never a universal default. First-sequence bulk true-loss recovery is 53.228969 ms in both controls, while selected whole goodput decreases 0.1016%. See the experiment document for exact scopes and active selective waiting; compatibility `guard_starts=0` does not mean selective inactivity.

The five-case safety stage was prospectively declared and selected before its runs. Final/source/runtime/input/output hashes, zero failed or excluded simulations, simulation-free development build, actual native rates, exact state integrals and prior-delivery witnesses are retained in [evidence](../../docs/experiments/assets/20261013-queue-pacing). Publication and Git writes are owned by the parent chat.

For a fresh official container/source volume on the same pinned image, install the complete artifact, compare the generated patch, then build synchronously:

```sh
python3 -B /work/code/queue-pacing/install.py --out /tmp/replay-queue-pacing.patch
cmp /tmp/replay-queue-pacing.patch /work/code/queue-pacing/ns3.patch
python3 -B /work/code/queue-pacing/build.py --out /tmp/replay-ready.json
python3 -B /work/code/queue-pacing/run.py off native capacity --root /tmp/queue-pacing-replay --ready /tmp/replay-ready.json --checkpoint YOUR_SOURCE_CHECKPOINT --timeout 600
python3 -B /work/code/queue-pacing/analyze.py --root /tmp/queue-pacing-replay --out /tmp/queue-pacing-replay-export --cases off native capacity
python3 -B /work/code/queue-pacing/compare.py --export /tmp/queue-pacing-replay-export --out /tmp/queue-pacing-replay-selection.json
```

The runner refuses an active build, stale runtime/source/readiness, existing output directory or a safety stage without a passing prospectively selected receipt. Review the selection before executing the five declared safety cases with `--selection`; no arbitrary rates or expanded matrix are provided. Observers do not add simulator events, but direct retransmissions and the native unpaced initial window prevent this from being a strict aggregate wire shaper.
