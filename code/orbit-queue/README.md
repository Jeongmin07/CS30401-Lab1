# Paired 75-second queue-cause observation

Read the [predeclared diagnostic](../../docs/experiments/20261013-orbit-queue.md). This track adds passive device-queue, serialization and source TrafficControl/NetDeviceQueue identity/reason observations to the exact final orbit-loss V2 stack. It does not change CUBIC, loss waiting, geometry or pacing.

The initial pair preserves the original 200-second natural baseline/selective conditions. Old measurement equality is required before causal interpretation. At most one separately reviewed routing-delay counterfactual may follow; no new topology or active cap policy is included.
Use the pinned official image and a separate volume. Apply `ns3.patch` once to the clean official source, intent-add its scratch files, and build with one job. `install.py` can instead compose the exact frozen V2 base and passive observers. The initial natural pair uses the source checkpoint recorded in its manifests.

```text
python3 -B code/orbit-queue/run.py base-natural selective-natural --root /tmp/orbit-queue --timeout 600 --checkpoint <shared-checkpoint>
python3 -B code/orbit-queue/analyze.py --root /tmp/orbit-queue --out <new-summary.json>
```

`delay_route.py` constructs only the declared T75→T78 sparse routing input and validates accumulated paths/native interfaces. `run_cf.py` requires its reviewed receipt and a separate source checkpoint; it keeps the original selective forecast/hints unchanged. Input construction alone does not authorize its simulation. All tools refuse overwriting run or evidence outputs.

See [the declaration and measured boundary](../../docs/experiments/20261013-orbit-queue.md). Raw artifacts remain outside Git; publication is recorded by the parent chat.
