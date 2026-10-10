"""Draw standalone figures from the committed small evidence (course matplotlib)."""
import argparse
import csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence", type=Path, required=True)
    a = p.parse_args()
    with (a.evidence / "original-audit" / "delivery_timeline.csv").open() as f:
        timeline = list(csv.DictReader(f))
    with (a.evidence / "results.csv").open() as f:
        rows = {r["case"]: r for r in csv.DictReader(f)}
    plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(9, 4.4), layout="constrained")
    ax.plot([float(r["end_s"]) for r in timeline],
            [float(r["cumulative_delta_bytes"])/1000 for r in timeline], color="#245ea4")
    ax.axhline(0, color="#777", linewidth=0.8)
    for time, label in ((26.2, "first route event"), (121.6, "later route event")):
        ax.axvline(time, color="#b66a24", linestyle="--", linewidth=1)
        ax.text(time+2, 250, label, rotation=0, fontsize=9)
    ax.set(xlabel="Simulation time (s)", ylabel="Extra receiver delivery (kB; 1 kB = 1,000 bytes)",
           title="Protecting only the first event: early gain, later deficit", xlim=(0,200))
    ax.annotate("Ends 474.72 kB below baseline", xy=(200,-474.72), xytext=(95,-610),
                arrowprops={"arrowstyle":"->", "color":"#444"}, fontsize=10)
    fig.savefig(a.evidence / "delivery_deficit.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1,2,figsize=(10,4.4),layout="constrained")
    groups = (("True first-packet loss, 22 MSS", ["fup-loss22-base","fup-loss22-k8-exempt21","fup-loss22-k20"],
               ["Baseline","Threshold 8*","Threshold 20"]),
              ("Synthetic reordering, 80 MSS", ["fup-step80-base","fup-step80-k8-exempt21","fup-step80-k20"],
               ["Baseline","Threshold 8*","Threshold 20"]))
    for ax, (title, names, labels) in zip(axes, groups):
        values = [float(rows[n]["completion_s"])*1000 for n in names]
        ax.bar(labels, values, color=["#777777","#245ea4","#b66a24"],width=0.6)
        ax.set(title=title, ylabel="Completion time (ms; lower is better)", ylim=(0,680))
        for x, value in enumerate(values):
            ax.text(x,value+12,f"{value:.3f}",ha="center",fontsize=10)
    fig.suptitle("Smaller threshold reduces the loss penalty, but misses the reordering benefit", fontsize=12)
    fig.supxlabel("*With the <=21-MSS exemption; these flows are above the cutoff.",fontsize=9)
    fig.savefig(a.evidence / "loss_tradeoff.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
