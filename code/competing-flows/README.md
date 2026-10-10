# Same-path CUBIC competition runner

This is a new experiment tool, not an experiment result. It reuses the course
`make_run.sh` and the canonical `../kim-study/ns3.patch`; it does not modify or
build ns-3. Apply that patch to a fresh official ns-3 volume and build first.
The runner uses Python's standard library only.

The defaults retain Seoul (1584) to London (1585), two 100-GB CUBIC transfers,
10-Mbit/s ISL/GSL links, 100-packet queues, no pacing, seed 123456789, and 200
seconds of the supplied state. Both flows start at zero by default. The mode
letters label flow 0 and flow 1: `DD`, `GD`, `DG`, or `GG`; `D` retains K3 and
`G` uses K20 in the existing absolute windows 26.1–26.5 and 74.9–75.3 seconds.
This comparison tests coexistence on one identical-RTT route, not general
fairness across paths or a uniquely located bottleneck.

Inside the prepared container, with the checkout mounted at `/work`:

```sh
python3 /work/code/competing-flows/run_competing.py same-start-dd --mode DD
python3 /work/code/competing-flows/run_competing.py same-start-gd --mode GD
python3 /work/code/competing-flows/run_competing.py same-start-dg --mode DG
python3 /work/code/competing-flows/run_competing.py join10-gd --mode GD --start1-s 10
```

Use `--parameters0` or `--parameters1` to override that flow's guard string
when its role is `G`. For example, `--parameters0 'study_threshold=8;study_windows=26100000000:26500000000|74900000000:75300000000'`.
Parameters for a `D` flow remain empty. Guard-window times are absolute
simulation times; they are not offsets from flow start.

The official schedule reader requires flow IDs 0 then 1 and nondecreasing
start times, so `--start0-s` must not exceed `--start1-s`. Exchange `GD`/`DG`
to change which starting position is guarded. The course single-forward
arbiter chooses the next hop solely by target node ID, so two connections
to the same endpoint share directed links and device queues at a given time.
Packets already in flight can cross a forwarding update at different times.
The scheduler installs one receiving sink per endpoint on port 1024; the
existing patch identifies its separate accepted connections and flow tags.

Outputs stay under `/tmp/cs30401-competing/<case>`, and existing cases are
never overwritten. `case.json` records per-flow settings, actual commands,
controlled environment, source revision, script/patch/binary/config/schedule
hashes, image digest, status, and runtime. Failure evidence is retained.
Pass the image digest verified with host Docker inspection as `--image-digest`
or `CS30401_IMAGE_DIGEST`; the default is the previously verified official
image digest, not a Docker check performed from inside the container.
If replaying an exported archive without Git, supply its full known revision
with `--source-commit`. Recorded script and patch hashes identify uncommitted
experimental files separately from the base revision.

Analyze each finished case with the existing analyzer, for example:

```sh
python3 /work/code/kim-study/analyze_study.py /tmp/cs30401-competing/same-start-gd \
  --path-truth /work/code/kim-study/path_truth_200s.csv --include-bins \
  --output /tmp/cs30401-competing/same-start-gd/analysis.json
```

Receiver `payload_bytes` are unique ordered application delivery. Compare
each flow and their sum over matched active intervals; do not sum the sink's
shared cumulative total once per connection. Check both flows' trace/tag
coverage, actual high-threshold activation, restoration costs, queue losses,
and retransmissions before interpreting delivery shares as fairness. A
deterministic role swap is a control, not an independent statistical repeat.
