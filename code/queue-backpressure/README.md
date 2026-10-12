# Native source queue controls

This track compares the existing source device queue with standard FIFO/backpressure and CoDel. It changes queue placement/management at Seoul node1584/device1, while preserving the selective CUBIC and tail policy, schedule, supplied routing, link rates and other queues. It is an environment control comparison, not a new TCP algorithm.

All three declared Stage1 runs completed. FIFO4+96 moved the original backlog into the qdisc without changing delivered bytes, combined queue area, actual source residence or loss count. Native-default CoDel greatly reduced average waiting, but whole goodput fell6.349454%; neither passed every prospective gate. No Stage2 physical-loss experiment or parameter tuning was run. See the [experiment record](../../docs/experiments/20261013-queue-backpressure.md), [small results](../../docs/experiments/assets/20261013-queue-backpressure/results.csv) and [full compact analysis](../../docs/experiments/assets/20261013-queue-backpressure/analysis.json).

## Fresh replay

Use a fresh dedicated container and empty ns-3 volume from the pinned official image `ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4`. Bind the team repository at `/work`; allocate two CPUs and4GiB, and compile with one job. The official source HEAD is `99bc6f733274475b7a6e804128651e17ee2a2536`. These commands run inside that container.

Apply **one combined patch** to clean official source. It already contains the exact tail base and passive overlay; do not apply an older patch first. Intent-to-add exposes the seven new files to the exact installed-diff check.

```bash
cd /home/ubuntu/ns-3.48
git status --porcelain
git apply --check /work/code/queue-backpressure/ns3.patch
git apply /work/code/queue-backpressure/ns3.patch
git add -N scratch/main_satnet/backpressure.h scratch/main_satnet/flow_observer.h scratch/main_satnet/old_flight_drop.h scratch/main_satnet/queue_observer.h scratch/main_satnet/service_observer.h scratch/main_satnet/study_drop_trace.h scratch/study_micro/study_micro.cc
python3 -B /work/code/queue-backpressure/build.py --out /tmp/queue-backpressure-fresh-ready.json
CHECKPOINT=$(git -c safe.directory=/work -C /work rev-parse HEAD)
python3 -B /work/code/queue-backpressure/run.py control100 fifo4-96 codel4-96 --root /tmp/queue-backpressure-fresh --ready /tmp/queue-backpressure-fresh-ready.json --checkpoint "$CHECKPOINT" --timeout 600
python3 -B /work/code/queue-backpressure/analyze.py --root /tmp/queue-backpressure-fresh --out /tmp/queue-backpressure-fresh-analysis.json
python3 -B /work/code/queue-backpressure/export.py --root /tmp/queue-backpressure-fresh --analysis /tmp/queue-backpressure-fresh-analysis.json --out /tmp/queue-backpressure-fresh-export
```

The initial status output must be empty. All output locations must be new; tools refuse overwriting completed evidence. A build/runtime is immutable during the three-case batch. The runner verifies the installed patch, all17 binary/library hashes and exact tail dependency, records commands/environment/source/input/output hashes, and preserves failed or timed-out attempts. Use the fresh build receipt through `--ready`; the tracked receipt describes the original build and must remain intact. A fresh binary SHA may differ across compilation environments; compare measurement behavior separately.

`install.py` is the source-generation recipe, while `ns3.patch` is the portable complete artifact. `development-initial/` preserves a source-only build before the coverage fix; it was never simulated and should not be replayed as a result. `reference-receipt.json` records an actual byte/hash check of the previous completed tail run and is used only for the no-qdisc control equivalence.

## Measurement contract

`bp_state_bins.csv` integrates exact source qdisc/device/requeue packet state into100ms bins; `weighted_device_queues.csv` measures every visited native device queue over the whole200 seconds. A4+96 configuration is a nominal queued capacity, not a strict100-resident-packet bound: the ordinary requeue slot and serializing packet are separately inventoried.

`bp_served.csv` measures actual TrafficControl ingress to device serialization start for each packet, including both layers and requeue time. CoDel drops after qdisc dequeue are excluded from served residence. `bp_outcomes.csv` retains dropped residence and censored pending ages. Source ingress, native qdisc/device counters, final pending state, packet areas and serialization busy time are reconciled. Queue-at-flush values are not substituted for integrated occupancy.

Loss counts are the union of **tagged payload-bearing transmitted data** at all covered layers, deduplicated by flow, tx_id, original TX time, sequence and payload length, and joined to actual sender TX. Deliberate CoDel drops are losses; zero device drops alone is not a benefit. ACK/control or untagged notifications are separately reported. The current three cases have zero unmapped notifications.

The whole, first `[25.7,28.2)`, post `[75,75.5)` and focus `[74.5,77.5)` windows use exact half-open event-time bounds. Served residence uses serialization-start event time; late pending and discarded packets have separate statistics. First-window reporting and explicit matched-input receipts were added only after all simulations, with the original launch helper SHA preserved.

Raw originals are separately archived with streamed member verification; the [common publication record](../../docs/experiments/20261013-queue-mitigation.md) maps published archives and checksums. One deterministic natural route trace per condition does not establish general performance or statistical significance.
