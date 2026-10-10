# CUBIC follow-up tools

Read the [experiment explanation](../../docs/experiments/20261010-cubic-followup.md) first. It contains the findings, small result tables, figures, raw-data download and complete PowerShell setup commands.

These scripts extend the existing `code/kim-study/` runner and analyzer. They do not introduce a new C++ patch. Run them inside the pinned course image after applying canonical `code/kim-study/ns3.patch` to a fresh ns-3 volume.

| Script | Purpose | Output |
| --- | --- | --- |
| `run_controls.py` | Run the 29 new conditions; `--stage originals` runs the two older comparison cases | Raw runs in `/tmp/cs30401-study/<case>/` and a batch execution JSON |
| `export_results.py` | Analyze all 31 completed cases and retain compact evidence | `results.csv`, `raw_hashes.json`, exact settings and compact case summaries |
| `compare_traces.py` | Compare original queue-75 baseline with first-event protection | Delivery timelines, drop/congestion rows, congestion-window checkpoints and source hashes |
| `verify_replay.py` | Compare an independent replay with published evidence | PASS/FAIL JSON covering settings, metrics, binary/patch hashes, full-analysis hashes and 279 raw-file hashes |
| `archive_traces.py` | Check raw hashes and compress exactly the 31 exported cases | A large `.tar.gz`; store outside Git and share through the linked release |
| `draw_figures.py` | Draw the report figures from small evidence | Two PNG figures; uses matplotlib already installed in the course image |

Run/export/archive scripts refuse to overwrite existing outputs. The exporter accepts `--reuse-analysis` only to retain existing analysis files. Use a fresh container to repeat case names. `--stage all` excludes `originals`; run both stages for a full 31-case replay.

In `results.csv`, `receiver_bytes` is ordered unique application delivery, `goodput_mbps` divides by the entire simulation duration, and `completion_s` is the last application delivery for a finished finite flow. Prefer completion time for the short synthetic transfers. Event columns use 2.5-second windows around the named route event. Drop rows and distinct dropped transmission tags are recorded separately.

Case names: `fup75` means queue 75; `start1` shifts the flow start to 1 s; `q50` changes queue capacity to 50 packets; `loss20/22` are genuine-loss tests for that many MSS; `step80` is the synthetic 80-MSS reordering test. `base` is unprotected, `k8/k9/k20` names the temporary threshold, and `exempt21` preserves threshold 3 for known transfers of <=21 MSS. Exact conditions always come from `case.json`, not the filename alone.
