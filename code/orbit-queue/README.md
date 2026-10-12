# Paired 75-second queue-cause observation

Read the [predeclared diagnostic](../../docs/experiments/20261013-orbit-queue.md). This track adds passive device-queue, serialization and source TrafficControl/NetDeviceQueue identity/reason observations to the exact final orbit-loss V2 stack. It does not change CUBIC, loss waiting, geometry or pacing.

The initial pair preserves the original 200-second natural baseline/selective conditions. Old measurement equality is required before causal interpretation. At most one separately reviewed routing-delay counterfactual may follow; no new topology or active cap policy is included.
