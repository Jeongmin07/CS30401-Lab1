"""Render the bounded v1 case study from compact, traceable evidence.

uv run --project code/vegas-study/report code/vegas-study/report/plot_results.py
All figures describe deterministic runs; no confidence intervals are invented.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
COLORS = {"base": "#305E83", "renew": "#BF682F"}
LABELS = {"base": "Original Vegas", "renew": "RTT-reference renewal"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def identity(path):
    return {"bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--view", type=Path, default=HERE / "evidence")
    parser.add_argument("--evidence", type=Path, default=HERE.parent / "evidence")
    parser.add_argument("--out", type=Path, default=HERE / "figures")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    timeseries = args.view / "timeseries.csv"
    preparation = json.loads((args.view / "preparation.json").read_text())
    require(identity(timeseries) == preparation["outputs"]["timeseries.csv"],
            "Changed prepared time series")
    results_path, queues_path = (args.evidence / name for name in
                                 ("results.csv", "queue_sojourn.csv"))
    require(identity(results_path) == preparation["input_results"], "Changed result table")
    rows, results, queues = read_csv(timeseries), read_csv(results_path), read_csv(queues_path)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": "#252525", "text.color": "#252525",
                         "pdf.fonttype": 42, "svg.fonttype": "none",
                         "legend.frameon": False})
    outputs = []

    def save(fig, name):
        for suffix in ("png", "pdf"):
            path = args.out / f"{name}.{suffix}"
            fig.savefig(path, dpi=190, facecolor="white", bbox_inches="tight",
                        metadata={"Creator": "CS30401 Team 5: existing v1 evidence"})
            outputs.append(path)
        plt.close(fig)

    for family, title, events in (
        ("step", "Controlled propagation RTT: 90 to 96 ms at 100 s", (100.0,)),
        ("leo", "Supplied Seoul-London LEO path; one Vegas flow", (121.6, 187.4)),
    ):
        fig, axes = plt.subplots(3, 1, figsize=(8.6, 6.7), sharex=True,
                                 layout="constrained")
        for mode in ("base", "renew"):
            data = [row for row in rows if row["case"] == f"v1-{family}-{mode}"]
            require(len(data) == 200, "Incomplete one-second time series")
            t = [int(row["sample_time_ns"]) / 1e9 for row in data]
            centers = [(int(row["bin_start_ns"]) + int(row["bin_end_ns"])) / 2e9 for row in data]
            axes[0].plot(centers, [float(row["application_goodput_mbps"]) for row in data],
                         color=COLORS[mode], linestyle="-" if mode == "base" else "--",
                         label=LABELS[mode], linewidth=1.7)
            axes[1].step(t, [int(row["cwnd_bytes"]) / 1380 for row in data], where="post",
                         color=COLORS[mode], linestyle="-" if mode == "base" else "--",
                         linewidth=1.7)
            axes[2].step(t, [int(row["vegas_base_rtt_ns"]) / 1e6 for row in data], where="post",
                         color=COLORS[mode], linestyle="-" if mode == "base" else "--",
                         linewidth=1.7, label=f"{mode}: Vegas reference")
            axes[2].step(t, [int(row["socket_srtt_ns"]) / 1e6 for row in data], where="post",
                         color=COLORS[mode], linestyle=":" , alpha=.85,
                         linewidth=1.15, label=f"{mode}: socket SRTT")
        renewals = [row for row in read_csv(args.evidence / "renewals.csv")
                    if row["case"] == f"v1-{family}-renew"]
        for row in renewals:
            t = int(row["time_ns"]) / 1e9
            axes[2].scatter(t, int(row["base_rtt_ns"]) / 1e6, color=COLORS["renew"],
                            s=30, marker="D", zorder=5)
        for ax in axes:
            for event in events:
                ax.axvline(event, color="#777777", linewidth=1, linestyle=(0, (3, 3)))
            ax.grid(axis="y", color="#e4e4e4", linewidth=.6)
            ax.set_xlim(0, 200)
        axes[0].set_title(title, loc="left", fontsize=12, pad=9)
        axes[0].set_ylabel("App goodput\n(Mbit/s, 1-s bins)")
        axes[0].set_ylim(0, 105)
        axes[0].legend(loc="lower left", ncols=2, fontsize=9)
        axes[1].set_ylabel("Congestion window\n(MSS = 1,380 bytes)")
        axes[1].set_ylim(bottom=0)
        axes[2].set_ylabel("Delay (ms)")
        axes[2].set_xlabel("Simulation time (s)")
        axes[2].legend(loc="best", fontsize=8, ncols=2)
        save(fig, f"{family}-mechanism")

    # Equal common-active windows; no mixture with the 200-s solo denominator.
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.5), layout="constrained")
    x, width = np.array([0, 1]), .34
    categories = ["Fixed RTT", "RTT increase"]
    queue_export = []
    for mode, shift in (("base", -width / 2), ("renew", width / 2)):
        flow0, total, delay = [], [], []
        for family in ("fixed", "step"):
            case = f"v1-{family}-comp-{mode}"
            row = next(row for row in results if row["case"] == case and
                       row["window"] == "competition" and row["flow_id"] == "0")
            queue = next(row for row in queues if row["case"] == case and
                         row["window"] == "competition" and
                         row["direction"] == "forward" and row["group"] == "all")
            require((int(row["start_ns"]), int(row["end_ns"])) == (80_000_000_000, 200_000_000_000),
                    "Unequal competition comparison")
            flow0.append(float(row["application_goodput_mbps"]))
            total.append(float(row["application_sum_goodput_mbps"]))
            delay.append(float(queue["mean_ns"]) / 1e6)
            queue_export.append({"case": case, "window": "80-200s",
                                 "Vegas_Mbps": flow0[-1], "aggregate_Mbps": total[-1],
                                 "forward_packet_mean_queue_ms": delay[-1]})
        for ax, values in zip(axes, (flow0, total, delay)):
            bars = ax.bar(x + shift, values, width, color=COLORS[mode], label=LABELS[mode],
                          hatch=None if mode == "base" else "//", edgecolor="white")
            ax.bar_label(bars, labels=[f"{value:.2f}" for value in values], padding=3, fontsize=9)
            ax.set_xticks(x, categories)
            ax.set_ylim(0, max(values) * 1.22)
            ax.grid(axis="y", color="#e4e4e4", linewidth=.6)
            ax.set_axisbelow(True)
    for ax, ylabel in zip(axes, ("Vegas goodput (Mbit/s)", "Aggregate goodput (Mbit/s)",
                                "Forward queue sojourn (ms)")):
        ax.set_ylabel(ylabel)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Vegas + unchanged CUBIC: common active interval, 80-200 s", fontsize=12)
    save(fig, "competition-costs")
    values_path = args.out / "competition-values.csv"
    with values_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(queue_export[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(queue_export)
    outputs.append(values_path)
    receipt = {"no_new_simulations": True, "script": identity(Path(__file__)),
               "matplotlib_version": matplotlib.__version__, "numpy_version": np.__version__,
               "inputs": {name: identity(path) for name, path in (
                   ("prepared_timeseries.csv", timeseries),
                   ("v1_results.csv", results_path),
                   ("v1_queue_sojourn.csv", queues_path),
                   ("v1_renewals.csv", args.evidence / "renewals.csv"))},
               "outputs": {path.name: identity(path) for path in outputs}}
    (args.out / "figures.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"figures": 3, "formats": ["png", "pdf"],
                      "no_new_simulations": True}))


if __name__ == "__main__":
    main()
