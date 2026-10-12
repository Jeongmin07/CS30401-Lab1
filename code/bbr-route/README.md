# Modern TCP diagnostic tools

Read [the current plan](../../docs/PLAN.md) and [the work record](../../docs/work/20261012-bbr-route-kim-seongchan.md) first. The initial hypothesis that bandwidth reduction after route convergence alone establishes a LEO-specific problem has been **stopped**. These tools preserve its bounded checks and a validated passive observer; no congestion-control improvement is implemented here.

## What has actually run

- `path_probe.py`: applies incremental forwarding files and walks selected existing routes under explicit read/time budgets.
- `geometry_probe.py`: uses sparse single-source shortest paths for two declared city groups and eight times. Both reproduce the original Seoul/London paths. Neither found a sampled merge/split candidate; unsampled intervals remain unknown. `NOTES.md` records full costs and the archived earlier tool version.
- `observability.py` / `ns3-observe.patch`: passive, opt-in BBR state, actual application delivery, queue visits, pending packets and layered drops. The patch changes no TCP policy or wire header. The original and observer-off/on single-flow runs have four byte-identical legacy measurement CSVs.
- `run_pilot.py`: predeclared 40-second shared-path diagnostics, **not natural convergence experiments**. Reference/off/on single-flow runs completed. A faulty first observer attempt was corrected; the two-flow run timed out at its 180-second budget and the simultaneous-start case did not run. Failed/partial files are excluded from performance analysis.
- `analyze_pilot.py`: verifies observer input hashes, flow/connection identities, application totals and queue conservation before summarizing declared windows. ACK samples, actual delivery and drop layers remain separate.
- `archive_raw.py`: preserves text raw runs and receipts outside Git, including clearly identified unsuccessful attempts.

The implemented observer patch is SHA256 `ddcad50d06a8e3fc34a79fabb4942e2225d4788488d3db96e2b72a379262c445`. Earlier UID-based observer code is historical and must not be used; Packet UID is shared by TCP fragments, so current queue tracking uses the actual queued packet object.

## Reproduce the completed single-flow measurement

Use a new container and empty volume. Run from the repository root; change the two names if they already exist. The reference requires **all original build libraries**, since copying only the binary would still load newly built libraries through its RUNPATH. The runner explicitly selects the corresponding library directory.

```powershell
$routeTaskRoot = (Resolve-Path .).Path
$routeTaskImage = 'ghcr.io/yeonjong21/cs30401-lab1@sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4'
docker run -d --name bbr-route-replay --cpus 4 --memory 6g --mount "type=bind,source=$routeTaskRoot,target=/work" --mount 'type=volume,source=bbr-route-replay-ns3,target=/home/ubuntu/ns-3.48' $routeTaskImage sleep infinity
docker exec bbr-route-replay bash -lc 'mkdir -p /tmp/bbr-route-reference && cp -a /home/ubuntu/ns-3.48/build /tmp/bbr-route-reference/build'
docker exec bbr-route-replay python3 /work/code/bbr-route/run_pilot.py reference-solo --root /tmp/bbr-route-replay
docker exec -w /home/ubuntu/ns-3.48 bbr-route-replay bash -lc 'git apply --check /work/code/bbr-route/ns3-observe.patch && git apply /work/code/bbr-route/ns3-observe.patch && git add -N scratch/main_satnet/bbr_route_observer.h && ./ns3 build -j 4'
docker exec bbr-route-replay python3 /work/code/bbr-route/run_pilot.py patched-off-solo observed-solo --root /tmp/bbr-route-replay
docker exec bbr-route-replay python3 /work/code/bbr-route/path_probe.py --state /home/ubuntu/lab/data/seoul_london/state --out /tmp/bbr-route-replay-path
docker exec bbr-route-replay python3 /work/code/bbr-route/observability.py compare --reference /tmp/bbr-route-replay/reference-solo --observed /tmp/bbr-route-replay/observed-solo --state-receipt /tmp/bbr-route-replay-path/path-probe.json --out /tmp/bbr-route-replay-equivalence.json
docker exec bbr-route-replay python3 /work/code/bbr-route/analyze_pilot.py /tmp/bbr-route-replay/observed-solo --out /tmp/bbr-route-replay-analysis
```

These are commands for reproducing the completed condition, not a claim that this entire command block was rerun in another fresh volume. Initial measurements used the fresh official volume recorded in the work log. No new two-flow run is needed for the stopped hypothesis. The runner never overwrites existing case directories.

## Interpretation boundaries

`bbr_state.csv` samples cached state after ACK processing, at most once per 100ms bucket plus mode/gain transitions. It is not every raw RTT observation or an exact cutoff loss total. The application CSV records unique in-order bytes returned by `RecvFrom` and bins them by actual delivery time. Coverage includes drop-before-admission at `TrafficControlLayer`, device queues and IPv4; hook event counts cannot be summed as unique lost transmissions.

Queue wait is measured for each served device-queue visit, including zero waits and both data/ACK directions. It is **not end-to-end queuing delay**. `flush_time_ns` identifies when occupancy was read; that occupancy is not a historical bin-boundary sample. Remaining queue packets are separately censored and enqueue/dequeue/pending totals are checked. A present root QueueDisc or DropAfterDequeue is outside this observer's supported queue interpretation and causes a failure.

The source/geometry screen of RTprop and HyStart is an analytic feasibility check, not a TCP performance experiment. `TcpBbr` is BBRv1-family; the CUBIC/SACK stack lacks modern Linux RACK-TLP. All claims retain the provided implementation and model scope.
