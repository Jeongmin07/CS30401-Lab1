# Rebuild the English IEEE report

Run these commands from the **extracted submission**, whose layout is `README.md` plus `code/`. No repository checkout or historical research container is required. The top-level README builds and executes the two fixed runtime profiles; finish both before regenerating report data. The main proposed profile is selective loss waiting plus the one-MSS final-segment allowance, pacing OFF. Pacing and FIFO/CoDel are diagnostic controls.

## Fresh figures and numerical table

Both profile analyzers read their new raw traces and enforce historical measurement parity. Their normalized files are `/work/output/lab1-final-replay/{pace,bp}/report-data.json`. Merge and generate with the supplied locked environment:

```bash
docker exec lab1-final-pace python3 -B /work/code/merge.py --pace /work/output/lab1-final-replay/pace/report-data.json --bp /work/output/lab1-final-replay/bp/report-data.json --out /work/output/lab1-final-replay/report-data.json
docker exec lab1-final-pace uv sync --project /work/code --frozen
docker exec lab1-final-pace uv run --project /work/code --frozen python /work/code/report/build_figures.py --data /work/output/lab1-final-replay/report-data.json --out /work/output/lab1-final-replay/figures
docker exec lab1-final-pace uv run --project /work/code --frozen python /work/code/report/build_tables.py --data /work/output/lab1-final-replay/report-data.json --out /work/output/lab1-final-replay/tables
docker exec lab1-final-pace python3 -B /work/code/report/audit_witnesses.py --root /tmp/lab1-final-pace --export /work/output/lab1-final-replay/pace --out /work/output/lab1-final-replay/witnesses.json
```

Use unused output directories; figure/table tools refuse overwriting. Stage the verified new PDFs and `magnitudes.tex` in `code/report/figures/` and `code/report/tables/` before compilation, preserving supplied originals or using a separate report-directory copy. Standard-library runners/analyzers and the locked Matplotlib 3.10.8 environment have separate responsibilities. Figures do not launch simulations. PDF clock metadata is omitted; same-version deterministic regeneration can be checked by hashes.

| Report item | Actual input fields / fixed specification |
|---|---|
| Figure 1: window around 26.2 s | `report_roles.stock_bulk/tail_bulk` → `cases[id].figure_series.cwnd`; actual time/cwnd steps, 1380 B MSS conversion and held endpoint. |
| Figure 2: four finite FCTs | `stock_finite/selective_finite/tail_finite/capacity_finite` → `metrics.fct_s`; validates complete expected-byte delivery. |
| Figure 3: source backlog | `stock_bulk/tail_bulk/route_delayed/capacity_bulk` → `figure_series.source_queue_bins`; all 30 exact 100 ms packet-time bins over `[74.5,77.5)`, source 1584/device 1. |
| Table I: experiment specification | `code/common.py` → `CASES`, `ALIASES`; every fixed case/definition is emitted in `table-I-spec-map.csv`. Fresh analysis checks actual manifests against those declarations. Micro CLI defaults/configuration are in `run.py` and each actual manifest. |
| Table II: effect magnitudes | Finite roles → `metrics.fct_s`, `tail_admissions`; bulk roles → `metrics.receiver_goodput_mbps`, `distinct_tagged_drops`. `build_tables.py` emits 7 numerical rows and the exact included `magnitudes.tex`. |

Each generated directory has a receipt with input/helper/output hashes. `tables/values.json` also maps manuscript sections to fresh metrics, windows, loss identities, queue fields and episode records. `witnesses.json` independently joins original TX, receiver acceptance, ordered application delivery and later RETX for the reported episodes, and records finite first-RETX/last-new-data chronology. The manual descriptive Table I is a fixed setup overview, not a performance table or a fit to observed outcomes.

## Numeric statements by section

- **Introduction/Problem Statement:** prior-work and source mechanisms; original delivery requires receiver/application/ACK evidence, not geometry alone.
- **Proposed Ideas:** executable forward-hint horizon/wait/budget and tail eligibility from frozen policy sources; not result-dependent hyperparameters.
- **Experiment Setup:** `common.py` case/alias map plus actual manifest command/config/schedule/state hashes; 19 physical conditions and 3 aliases, not 22 distinct simulations.
- **Evaluation A / Figure 1:** stock/selective/tail bulk `metrics`, `windows.first`, `windows.legacy`, and `selective_episodes`. Whole extra bytes and relative goodput change are computed in `values.json`.
- **Evaluation B / Figure 2 / Table II:** finite `metrics` and `tail_admissions`, 21-MSS boundary cases, and `leo10-drop-base/leo10-drop-tail.actual_drop`. The old-flight first-RETX delay is relative to the matched physical drop, not full recovery duration.
- **Evaluation C / Figure 3:** actual source queue pre/post/focus, native stop/drop identity and `route_delayed` series, with the separate exact pre75/input-validity receipts. SRTT is not queue residence; the route control changes two-direction/link choices under the ideal channel model.
- **Evaluation D / Table II:** `capacity`, `native`, and current bulk metrics/queues; `loss-current/loss-selected.actual_drop`; `micro-selected.native_pacing` and finite metrics. CoDel drops remain in all-layer data loss totals. Source queue zero does not imply zero downstream queues.

The report's scalar values must remain equal to the freshly analyzed cases and supplied parity contract. That contract is a validator, never the source of plots/tables. The complete comparison distinguishes byte-identical measurement files from exactly three `bp_outcomes.csv` files: their non-pending rows remain ordered-identical and their final pending records match as full-field multisets. The pointer-ordered pending serialization is the sole order-insensitive exception; original raw byte hashes and the initial strict-comparison failure are retained, and no simulator/policy or run was changed. Final fresh receipts state the exact validated file count and the postprocessing-only helper version.

All-layer loss totals are tagged payload-bearing transmitted data; ACK/control or unmapped notifications are separately qualified. Finite FCT requires completion; 200 s bulk does not have a completed-file FCT.

## Compile and inspect

`report.tex` uses actual IEEEtran conference defaults: two columns, 10pt body, unchanged margins/fonts/spacing, six required sections and ordinary references. Authors: Seongchan Kim, Jeongmin Kim, Jaehwan Kang; Team 5, CS30401 Fall 2026. The checked compiler is TeX Live 2023/Debian with IEEEtran 1.8b and Times. Install `texlive-latex-base`, `texlive-latex-recommended`, `texlive-fonts-recommended`, `texlive-publishers`, and **`texlive-latex-extra`** (`balance.sty`).

Compile twice from the report directory, using a new build directory:

```bash
cd code/report
mkdir -p /tmp/lab1-report-build-new
pdflatex -halt-on-error -interaction=nonstopmode -output-directory=/tmp/lab1-report-build-new report.tex
pdflatex -halt-on-error -interaction=nonstopmode -output-directory=/tmp/lab1-report-build-new report.tex
```

The source includes `figures/*.pdf` and `tables/magnitudes.tex`, so use a multi-file compiler. Render and inspect every page for readable charts/tables, clipping, overlap, references and balanced final columns. Body must remain within six pages; references may lie outside that limit. Build success, visual/page-count QA, fresh measured parity and archive verification are separate checks. Historical preflight notes are Git-only authoring records and are omitted from the submission ZIP.
