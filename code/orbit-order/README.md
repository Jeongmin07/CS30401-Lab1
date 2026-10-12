# Forecast new-data hold: small matched experiment

This independent track holds only **new TCP data** around forecast path shortenings. It does not raise the loss threshold, pause RTO, or apply the predict-loss policy. The exact source is the combined `ns3.patch` (SHA256 `b34eb19f43b64ce2379ecff245f5632efaba78be5cc9bb2e72f420f070cdecd3`), including canonical-v6 tracing and micro controls.

In a fresh official-image ns-3 volume at HEAD `99bc6f733274475b7a6e804128651e17ee2a2536`, apply this **one** patch. Do not stack it with canonical v6 or another study patch. The installer is the historical composition tool, requiring exact canonical-v6 source; it is unnecessary when applying the exported combined patch.

```bash
cd /home/ubuntu/ns-3.48
git apply --check /work/code/orbit-order/ns3.patch
git apply /work/code/orbit-order/ns3.patch
git add -N -- scratch/main_satnet/study_drop_trace.h scratch/study_micro/study_micro.cc
git diff --check
./ns3 build -j 1
python3 -B /work/code/orbit-order/run.py leo10-base leo10-hold1 leo10-hold2 loss-first-base loss-first-hold --root /tmp/orbit-order --timeout 240
```

The runner refuses existing run directories and rejects a source diff different from the combined patch. Preserve the runtime binary/library hashes and exact runner from the manifests. The five actual runs used repository commit `8fd57045e616c29202cc3fd79d4a06fa4cabf777`, runner SHA `21e1554c20fa459bfbf49caa642564f7cc6765e388ad2afb472b32e8e06cfc3b`, and the existing geometry SHA `49bd5418f2b13bdbf6d703f719d61075f814cc86d44c745651bf797f4e5f656c`. The concurrent tracks caused `repo_dirty=true`; each run identifies the actual installed source and runtime separately.

For each LEO run, use the unmodified canonical analyzer with `--path-truth /work/code/kim-study/path_truth_200s.csv --include-bins --output RUN/analysis.json`. For the two micro runs use `--events 2 --include-bins --output RUN/analysis.json`. Example:

```bash
python3 -B /work/code/kim-study/analyze_study.py /tmp/orbit-order/leo10-base --path-truth /work/code/kim-study/path_truth_200s.csv --include-bins --output /tmp/orbit-order/leo10-base/analysis.json
python3 -B /work/code/kim-study/analyze_study.py /tmp/orbit-order/loss-first-base --events 2 --include-bins --output /tmp/orbit-order/loss-first-base/analysis.json
python3 -B /work/code/orbit-order/summarize.py --root /tmp/orbit-order --out /tmp/orbit-order-export
python3 -B /work/code/orbit-order/compare.py --export /tmp/orbit-order-export --historical /work/code/kim-study/evidence/cases/leo10-base/summary.json
```

The source gate checks the next TCP sequence against the already-transmitted high-water mark after segment selection. It retains marked retransmission paths and cancels its separate wake timer on close/dispose. ACK-clock/SACK feedback can still make real loss completion slower; preserving the direct recovery code does not guarantee no indirect cost.

All five runs completed. LEO goodput/reordering/retransmissions did not improve. The stable 20-MSS true-first-loss control completed in `0.251509920 → 0.362097200` seconds (**+43.97% FCT**). Exact declarations, actual hold intervals, matched outputs, and limitations are in [the experiment](../../docs/experiments/20261012-orbit-order.md) and its compact assets. No direct blocked-send-opportunity counter, independent replay, seed repetitions, new topology, or parameter sweep was run. SRTT is not a direct queue-wait measurement.
