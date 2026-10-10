# Existing v1 results: English brief and reproducible figures

Start with [RESEARCH_BRIEF.md](RESEARCH_BRIEF.md). It narrows the research to first-renewal gains and the queue-ambiguity counterexample. It is review material, not the final IEEE report or course submission.

## Inputs and outputs

- Simulation code/launch: `82ad34a975d4b15f8a536527f8ea4f0cf6e41624`; complete v1 patch SHA-256 `25ac4286f68373ee4e33d43f5f00e8676a65fc9c8747d65f643cd0fc28202f59`.
- Existing measurement/evidence snapshot: `8ce7ea6c9f0d9b91c716ca61880bb0187a6b08e3`, `code/vegas-study/evidence/`.
- [Published v1 raw archive](https://github.com/Jeongmin07/CS30401-Lab1/releases/tag/vegas-renewal-20261010), SHA-256 `5f63e78ef2eec9c5206b16185c9595617d54257a836863b8139367c9eea77723`. Extract its paths and locate the directory containing `v1-step-base`, `v1-step-renew`, `v1-leo-base`, `v1-leo-renew`; pass that parent as `--raw-root`.
- `prepare_results.py` uses only the standard library, verifies 16 used raw measurement files and four simulation manifests against the published case-summary hashes, and independently sums receiver app bytes. It does not call a simulator or modify the source measurements.
- `evidence/timeseries.csv`: 800 rows, four cases × 200 one-second bins; app delivery and separately sampled TCP state.
- `evidence/segments.csv`: ten exact time segments, including controlled before/after and LEO temporal accounting.
- `evidence/preparation.json`: source hashes, simulation identity, transformation and byte-total checks.
- `figures/`: three PNG/PDF pairs, exact plotted competition values, and figure input/output hashes.

## Recreate the compact evidence

Run from the repository root with Python 3.12+:

```bash
python3 code/vegas-study/report/prepare_results.py \
  --raw-root /tmp/cs30401-vegas \
  --out /tmp/vegas-report-view
```

Use an empty output directory. Existing committed view files need not be overwritten. On this machine the retained v1 container has `/tmp/cs30401-vegas`; another laptop must obtain the archive or reproduce the original runs using the [v1 runner](../README.md). The preparation checks that every used input is the published original rather than silently mixing later runs.

## Recreate the three figures

The plotting dependency project is isolated in this folder, with `pyproject.toml` and a `uv.lock`. It does not alter simulation dependencies or TCP code.

```bash
uv run --locked --project code/vegas-study/report \
  code/vegas-study/report/plot_results.py
```

To render a newly prepared view without overwriting committed figures:

```bash
uv run --locked --project code/vegas-study/report \
  code/vegas-study/report/plot_results.py \
  --view /tmp/vegas-report-view --out /tmp/vegas-report-figures
```

The renderer records its own script and library versions. It verifies that the prepared time-series and main result inputs match the preparation receipt. Images need not be byte-identical across platforms; numerical source verification is separate from rendering.

| Brief figure/table | Source and regeneration |
|---|---|
| Single-flow full-200-s result table | Existing `../evidence/results.csv`: flow 0, `whole`, three solo scenarios |
| Controlled [0,100)/[100,200) text | `prepare_results.py` → `segments.csv`; exact receiver app bytes |
| LEO temporal-accounting table | `prepare_results.py` → `segments.csv`; fixed cuts 121.6/187.4 s; no causal attribution |
| Controlled mechanism | `plot_results.py` → `step-mechanism.png/pdf` |
| LEO mechanism | `plot_results.py` → `leo-mechanism.png/pdf` |
| Competition cost table | Existing `results.csv` / `queue_sojourn.csv`, common `competition` window |
| Competition figure | `plot_results.py` → `competition-costs.png/pdf`, `competition-values.csv` |

Goodput is receiver app bytes over the specified duration. Queue means are packet weighted and measured in the controlled topology; no LEO queue measurement is invented. All inputs describe deterministic runs, so no statistical intervals are attached. No new policy, parameter tuning, or simulation is included in this result-preparation change.

The final submission ZIP workflow, IEEE formatting and team author names remain unfinished. In particular, the original simulation runner expects Git provenance; the eventual ZIP wrapper needs an explicit non-Git source manifest and clean-environment validation. This review bundle must not be labelled submission-ready.
