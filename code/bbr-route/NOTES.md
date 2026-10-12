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

## On-demand geometry screening

`geometry_probe.py` is a separate, bounded screening tool. It uses the supplied
TLEs, ISL-file order, description range limits and official satgen GS-distance
function. It reproduces the course generator's cached ephem ISL-weight math,
one free GSL interface per node, all visible attachment candidates and the
free-one shortest-path/tie decisions. It caches length vectors from a
single-source Dijkstra for each distinct visible destination satellite. It
never runs all-pairs shortest paths, exports full forwarding state, or simulates
packets. Import/loader cost is included in elapsed time; the default cap is
100 seconds, 1,000 Dijkstra calls, 4 MiB of metadata/source fingerprint reads,
eight snapshots and 64 hops per route. Loader rereads are separately counted;
Python import IO and physical disk IO are not measured.

First, it compares both existing Seoul/London directions at all eight samples
against `path_probe.py`'s forwarding-derived nodes and directed egresses. A
mismatch stops the probe; no additional-city route is then promoted to routing
evidence. Destination-rooted networkx Dijkstra can differ numerically from
the official source-rooted scipy APSP, so sampled agreement is checked rather
than assumed to prove equivalence everywhere.

The first declared additional group is Seoul->London versus Tokyo->Paris. Tokyo
and Paris coordinates come from the installed Hypatia population-city input
file, with its hash recorded. Their node IDs are hypothetical in-memory IDs:
these stations do not exist in the supplied forwarding state. The alternative
paper-city group New York->London versus San Diego->St Johns was not evaluated;
St Johns is absent from that installed city dataset. There is no global
city/route search or unreported parameter sweep.

```text
python3 /work/code/bbr-route/geometry_probe.py --state /home/ubuntu/lab/data/seoul_london/state --out /tmp/bbr-geometry-probe
```

Eight snapshots produced exact agreement for all sixteen original-direction
references using 260 SSSP calls. The two additional independent-endpoint
corridors shared 3, 7, 1, 1, 6, 3, 3 and 3 directed ISLs at the declared sample
times; none of those samples showed fully separate ISL paths. At 100 s they
also shared satellite224's GSL outgoing interface4, although their destination
GSs differ. This is separately recorded and must not be mistaken for an ISL
edge. A sampled merge/split candidate was therefore not found. Behavior between
samples, exact four-GS exported forwarding and actual bottleneck/queue use
remain unverified. The script and `geometry-probe.json`, `geometry-paths.csv`
and `geometry-overlaps.csv` preserve the hypotheses and their measured cost.

### Second and final declared city group

Before execution, the second group is changed from New York->London versus
San Diego->St Johns to **New-York-Newark->London versus San-Diego->Paris**.
St Johns is absent from the installed coordinate dataset. The replacement
uses four distinct endpoints whose coordinates all exist in that same dataset,
preserving the transatlantic/long-US-corridor motivation without introducing
unverified coordinates. It is an exploratory corridor selection, not a
replication of a paper's terminals. The two-group maximum and the original
eight sample times remain fixed. No further city combinations or denser time
grid will be searched in this bounded step.

Only the declared group selector is added to the geometry tool; graph weights,
visibility, attachment choices, SSSP cache and path-walking decisions do not
change. The first completed receipt remains untouched. Its exact tool source
is archived as `geometry-asia-source.py` alongside that receipt, with SHA256
equal to its `script_sha256`. The newer selector source has its own hash.
The tool's automatic Seoul/London validation will run again in the second
calculation; this is a routing check, not an independent TCP experiment.

```text
python3 /work/code/bbr-route/geometry_probe.py --state /home/ubuntu/lab/data/seoul_london/state --corridors us-europe --out /tmp/bbr-geometry-us-europe
```

Second-group results will be recorded separately as
`geometry-us-europe-probe.json`, `geometry-us-europe-paths.csv` and
`geometry-us-europe-overlaps.csv`.

The second calculation completed in 5.0254 s including imports and TLE loading,
with 260 SSSP calls, 12,672 cached ISL position computations and 63,360 GSL
distance calls. Its automatic original-route check again matched all sixteen
reference node/egress paths. New York->London and San Diego->Paris were both
reachable but had no shared directed ISL, directed egress or GSL egress at
any of the eight declared samples. Thus the second sampled merge/split
candidate count is also zero. This does not establish absence between samples.

The two retained geometry receipts report 5.8389 s and 5.0254 s respectively
(10.8643 s combined). A prior first-group development/validation run took
5.6708 s before the fingerprint-budget guard was tightened; it used the same
cities and times, changed no path result, remains only in the container, and
is not an additional corridor or independent experiment. Including that
development run, observed geometry-tool elapsed time was about 16.5351 s.
No third corridor, denser grid, full forwarding export or TCP simulation was
run by these discovery tools. All three copied output receipts and the archived
first source hash were checked against the final host-file bytes.
