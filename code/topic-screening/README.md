# Alternative-topic pilot evidence

Exploratory ordinary-Vegas runs for [PR13](https://github.com/Jeongmin07/CS30401-Lab1/pull/13), not a validated fix/final submission. See the [research record](../../docs/research/20261010-new-topic-screening.md).

Simulation source at launch: `76885d178cd28838e9d4f97a23836cffb3cde7fc`. Use the official `2026f-v1` image and existing `code/kim-study/ns3.patch`, SHA-256 `473dd0e23447a58bd7ce644507cf4aa24b612020ff1e6029f5bfdb22e2cd4245`, applied/built using the course and [kim-study instructions](../kim-study/README.md). `/work` mounts this repository. This pilot reused a retained patched volume; it has not been freshly rebuilt/replayed for this branch.

## Exact original commands inside the container

Run IDs must be unused; the runner refuses existing output.

```bash
python3 /work/code/kim-study/run_study.py topic-vegas-q100-100m-dynamic --cc TcpVegas --rate 100 --queue 100 --duration 200 --trace 1
python3 /work/code/kim-study/run_study.py topic-vegas-fixed90ms --kind micro --cc TcpVegas --rate 100 --queue 100 --duration 20 --before-ms 45 --after-ms 45 --event-s 5 --trace 1
python3 /work/code/kim-study/run_study.py topic-vegas-step90to97ms --kind micro --cc TcpVegas --rate 100 --queue 100 --duration 20 --before-ms 45 --after-ms 48.5 --event-s 5 --trace 1
```

The last command reproduces the original **nominal setting**, truncated by the retained C++ micro driver to one-way 48 ms. Actual pure propagation RTT is 90→**96 ms**, despite the run name. Do not overwrite original records or silently change this interpretation. No loss is injected; blank TCP parameters mean ordinary Vegas with no threshold guard. Micro initial ssthresh is 900 MSS with ns-3 default RNG settings; the LEO config explicitly uses seed 123456789.

Observed runner wall times: 90.447 s, 0.567 s, 0.211 s, respectively. Raw output is about 270 MB; time depends on hardware/trace I/O.

```bash
/home/ubuntu/lab/.venv/bin/python3 /work/code/kim-study/analyze_study.py /tmp/cs30401-study/topic-vegas-q100-100m-dynamic --path-truth /work/code/kim-study/path_truth_200s.csv --include-bins --output /tmp/cs30401-study/topic-vegas-q100-100m-dynamic/analysis.json
/home/ubuntu/lab/.venv/bin/python3 /work/code/kim-study/analyze_study.py /tmp/cs30401-study/topic-vegas-fixed90ms --include-bins --output /tmp/cs30401-study/topic-vegas-fixed90ms/analysis.json
/home/ubuntu/lab/.venv/bin/python3 /work/code/kim-study/analyze_study.py /tmp/cs30401-study/topic-vegas-step90to97ms --include-bins --output /tmp/cs30401-study/topic-vegas-step90to97ms/analysis.json
```

The stdlib-only exporter independently sums ordered app bytes for `[start,end)` windows and verifies the original analysis total/manifest. It is added **after** simulation. Its source-commit argument supplements the missing original field using launch HEAD, without rewriting records. Window selection was diagnostic, not preregistered; each condition was run once. See `export_screen.py --help` for its exact CLI and `evidence/` for the validated small export.

```bash
python3 /work/code/topic-screening/export_screen.py --launch-commit 76885d178cd28838e9d4f97a23836cffb3cde7fc --out /tmp/cs30401-topic-screening-export-new
```

Original records, full analysis and per-file inventory: [Release archive](https://github.com/Jeongmin07/CS30401-Lab1/releases/download/leo-topic-screening-20261010/cs30401-topic-raw-20261010.tar.gz), 43,431,562 bytes, SHA-256 `39e45da2a0405bccc6e439debd947517634821cec2ab906451d56a669ced5f18`. No raw logs or ns-3 build tree are committed here.
