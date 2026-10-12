# Bounded discovery of existing forwarding paths

`path_probe.py` reads existing Hypatia state. It runs no simulator, generates
no state and changes no TCP implementation. It is a path-discovery aid, not
evidence of a congestion-control problem or improvement.

## Forwarding semantics and bounds

The course `scripts/path_truth.py` retains a forwarding dictionary between
time files. Files named `fstate_<time_ns>.txt` contain incremental five-column
updates `(source_node, destination_node, next_hop, outgoing_if, incoming_if)`.
Later files can be empty. Reading only eight isolated files would omit prior
updates and can produce incorrect paths. This tool instead applies every
update from time zero through the last requested sample. It retains entries
only for the selected destinations and walks only the selected routes.

The default is eight samples at 0, 20, 40, 60, 100, 140, 180 and 199.9 seconds.
It permits at most eight GS pairs, 2,000 forwarding-file opens, 16 MiB of
forwarding content, 2,000,000 forwarding rows, 1 MiB of metadata, 1,024 bytes
per forwarding line, 64 hops per route and 30 seconds of cooperatively checked
elapsed time. These are search budgets, not research parameters or performance
benchmarks. Limits and measured read costs are recorded. If a budget prevents
completion, exit status 2 and the receipt mark the completed prefix; an
incomplete search must not be reported as a global negative result.

No ordering assumption is used to stop file scans early. Every fully read
forwarding file receives its size, row count and SHA256 in `path-inputs.csv`.
Metadata hashes, tool hash and output hashes are in `path-probe.json`. Partial
input hashes are explicitly distinguished from full-file hashes, and partially
read updates are never applied. Read costs count logical file-content bytes,
not physical disk IO or simulation execution time.

## Use and output

Run inside the pinned official course container with a new output directory:

```text
python3 /work/code/bbr-route/path_probe.py --state /home/ubuntu/lab/data/seoul_london/state --out /tmp/bbr-path-probe
```

Without `--pair`, at most eight ordered pairs among the first four existing GS
nodes are inspected. This deterministic convenience selection is not a claim
that these cities match a paper. To specify actual metadata-verified GS nodes:

```text
--pair first:1584:1585 --pair second:1586:1587
```

The example second pair is valid only if those nodes exist in the chosen state;
the supplied Seoul/London state has only nodes 1584 and 1585. Nonexistent nodes
are rejected. The metadata, names and exact node IDs are always recorded.

Outputs are `path-samples.csv`, `route-overlaps.csv`, `path-inputs.csv` and
`path-probe.json`. The receipt also records route and overlap changes at every
applied update, including changes between the eight output samples. Pair
profiles distinguish same endpoints, reverse endpoints, ISL overlap and GSL
overlap. A merge/split candidate requires observed ISL sharing and non-sharing
for two corridors with four distinct GS endpoints. A common GSL is
reported separately: persistent shared endpoint service is not proof of an
intermittent ISL bottleneck. Same-direction flows with identical endpoints
follow the same deterministic forwarding path at each instant.

Directed edges and `(node, outgoing_if)` egresses are read from actual forwarding
entries. They establish possible overlap only. The tool does not assume queue
placement or link capacity, compute geometry, observe in-flight packets, or
establish that two flows actually contend. A useful candidate still needs
device/queue verification and a matched TCP baseline before experimentation.

## Observed supplied-state boundary

Initial metadata inspection in fresh `lab1-bbr-route-20261012` found 1,584
satellites and exactly two GSs: Seoul 1584 and London 1585. The initial
forwarding file is 55,792 bytes; inspected later updates at 0.1, 1, 20, 30 and
199.9 seconds are empty. Additional paper-city endpoint corridors do not
exist in this state. A two-flow staggered same-direction baseline is possible,
but it cannot demonstrate a natural merge/split between independent endpoint
corridors.

The completed probe applied all 2,000 updates through 199.9 s. Of these, 182
files were nonempty, containing 133,900 bytes and 7,614 rows in total. Including
the three metadata files, logical content read was 383,343 bytes; measured
elapsed time was 0.0931 s on this host. All sixteen requested directional paths
were reachable. Across all 2,000 states, the two opposite-direction routes had
no shared directed ISL or GSL edge. Each direction changed seven times, at 2.4,
26.2, 75.0, 121.6, 187.4, 193.8 and 194.0 s. The independent-endpoint candidate
count is zero. These are routing observations, not TCP experiment results.

Compact receipts are in
`docs/experiments/assets/20261012-bbr-route/{path-probe.json,path-samples.csv,route-overlaps.csv,path-inputs.csv}`.
The per-file inventory is about 208 kB and contains hashes and counts only,
not raw forwarding entries. No additional topology or state was generated.
