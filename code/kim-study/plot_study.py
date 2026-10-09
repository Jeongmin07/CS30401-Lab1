#!/usr/bin/env python3
"""Make publication figures from this study's receiver-based analysis.

Run inside cs30401-kim-study, where matplotlib is installed.  No simulator is
invoked.  Missing cases/traces are reported and never replaced by invented data.

Example:
  python3 /work/plot_study.py --runs-root /tmp/cs30401-study --out /work/figures

For preliminary, differently named runs:
  python3 /work/plot_study.py --case base=/tmp/cs30401-study/leo-cubic-base-v3 \
    --case guard=/tmp/cs30401-study/leo-cubic-guard20-v3 --causal base guard \
    --only causal --stage preliminary --out /work/figures/preliminary

Case arguments are KEY=FOLDER; --label KEY=TEXT controls displayed names.
An absolute input CSV path is used if it exists; otherwise its basename is
resolved under the case's logs_ns3 folder.  All plotted values come from the
specified flow.  Whole-run means include start-up and use the recorded duration.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D


COLORS = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#56B4E9"]
STYLES = ["-", "--", "-.", ":"]
DEFAULT_LABELS = {
    "leo10-base": "Cubic baseline",
    "leo10-static20": "Static threshold 20",
    "leo10-guard20": "Route guard 20",
    "leo10-late20": "Late notification guard 20",
    "leo100-base": "Cubic baseline",
    "leo100-static64": "Static threshold 64",
    "leo100-guard64": "Route guard 64",
    "micro-step-base": "Cubic baseline",
    "micro-step-static64": "Static threshold 64",
    "micro-step-guard64": "Route guard 64",
    "micro-loss-base": "Cubic baseline",
    "micro-loss-static64": "Static threshold 64",
    "micro-loss-guard64": "Route guard 64",
    "leo10-vegas": "Vegas baseline",
    "leo10-bbr": "BBR baseline",
}


def warn(message):
    print(f"WARNING: {message}", file=sys.stderr)


def assignment(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError("Expected KEY=VALUE")
    key, rest = value.split("=", 1)
    if not key or not rest:
        raise argparse.ArgumentTypeError("KEY and VALUE must both be nonempty")
    return key, rest


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def case_style(case, fallback=0):
    """Keep variant colors consistent between event, comparison and loss figures."""
    key = case.key.lower()
    if "late" in key:
        index = 3
    elif "static" in key or "vegas" in key:
        index = 1
    elif "guard" in key or "bbr" in key:
        index = 2
    elif "base" in key or "cubic" in key:
        index = 0
    else:
        index = fallback
    return COLORS[index % len(COLORS)], STYLES[index % len(STYLES)], index


@dataclass
class Case:
    key: str
    folder: Path
    label: str
    data: dict
    flow_id: str

    @property
    def flow(self):
        return self.data["flows"][self.flow_id]

    def input_path(self, kind):
        for item in self.data.get("inputs", []):
            if item.get("kind") == kind:
                original = Path(item["path"])
                fallback = self.folder / "logs_ns3" / original.name
                if original.exists():
                    return original
                if fallback.exists():
                    return fallback
        return None

    def legacy_path(self, suffix):
        path = self.folder / "logs_ns3" / f"tcp_flow_{self.flow_id}_{suffix}.csv"
        return path if path.exists() else None

    def event(self, time_s):
        matches = [e for e in self.data.get("path_event_windows", [])
                   if abs(float(e.get("time_s", -1)) - time_s) < 1e-6]
        return matches[0] if matches else None


def changes(path, scale=1.0, window=None):
    """Legacy ns-3 trace: flow_id,time_ns,value; preserve a pre-window point."""
    if path is None:
        return np.array([]), np.array([])
    xs, ys = [], []
    previous = None
    with path.open(newline="") as handle:
        for row in csv.reader(handle):
            if len(row) < 3:
                continue
            try:
                t, value = int(row[1]) / 1e9, float(row[2]) / scale
            except ValueError:
                continue
            if window and t < window[0]:
                previous = (window[0], value)
                continue
            if window and t > window[1]:
                break
            if previous is not None:
                xs.append(previous[0]); ys.append(previous[1]); previous = None
            xs.append(t); ys.append(value)
    if not xs and previous is not None:
        xs, ys = [previous[0]], [previous[1]]
    if window and xs and xs[-1] < window[1]:
        xs.append(window[1]); ys.append(ys[-1])
    return np.asarray(xs), np.asarray(ys)


def typed_rows(case, kind, events, window):
    path = case.input_path(kind)
    if path is None:
        return []
    output = []
    previous = None
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("flow_id") != case.flow_id or row.get("event") not in events:
                continue
            t = int(row["time_ns"]) / 1e9
            if t < window[0]:
                if kind == "state":
                    previous = row
                continue
            if t > window[1]:
                break
            output.append(row)
    if kind == "state" and previous is not None:
        initial = dict(previous)
        initial["time_ns"] = str(round(window[0] * 1e9))
        output.insert(0, initial)
    return output


def state_points(case, window):
    rows = typed_rows(case, "state", {"CONG"}, window)
    if not rows:
        # A constant state can be observed in the initialization event even when
        # the CONG change trace has no entries; never invent it for missing files.
        path = case.input_path("state")
        if path is not None:
            with path.open(newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("flow_id") == case.flow_id and row.get("cong_state"):
                        initial = int(row["cong_state"])
                        return np.asarray(window), np.asarray([initial, initial])
        return np.array([]), np.array([])
    xs = [window[0]]
    ys = [int(rows[0]["old_value"]) if int(rows[0]["time_ns"]) / 1e9 > window[0]
          else int(rows[0]["new_value"])]
    for row in rows:
        xs.append(int(row["time_ns"]) / 1e9)
        ys.append(int(row["new_value"]))
    xs.append(window[1]); ys.append(ys[-1])
    return np.asarray(xs), np.asarray(ys)


def goodput_points(case, window=None):
    bins = case.flow.get("receiver_application_bins", [])
    if not bins:
        return np.array([]), np.array([])
    selected = [b for b in bins if window is None or
                (float(b["end_s"]) > window[0] and float(b["start_s"]) < window[1])]
    if not selected:
        return np.array([]), np.array([])
    xs = [float(b["start_s"]) for b in selected] + [float(selected[-1]["end_s"])]
    ys = [float(b["goodput_mbps"]) for b in selected] + [float(selected[-1]["goodput_mbps"])]
    return np.asarray(xs), np.asarray(ys)


def coarse_goodput_points(case, bin_s, duration):
    """Aggregate complete fine bins; never interpolate delivery time or bytes."""
    bins = case.flow.get("receiver_application_bins", [])
    if not bins:
        return np.array([]), np.array([])
    totals = {}
    for entry in bins:
        start, end = float(entry["start_s"]), float(entry["end_s"])
        if end > duration + 1e-8:
            break
        index = math.floor((start + 1e-8) / bin_s)
        end_index = math.floor((end - 1e-8) / bin_s)
        if index != end_index:
            warn(f"{case.key}: requested coarse bins split source bins; using original goodput bins")
            return goodput_points(case, (0, duration))
        totals[index] = totals.get(index, 0) + int(entry["bytes"])
    if not totals:
        return np.array([]), np.array([])
    xs, ys = [], []
    for index, byte_count in sorted(totals.items()):
        start, end = index * bin_s, min(duration, (index + 1) * bin_s)
        xs.append(start)
        ys.append(byte_count * 8 / (end-start) / 1e6)
    xs.append(end); ys.append(ys[-1])
    return np.asarray(xs), np.asarray(ys)


def format_ax(ax, ylabel):
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#dddddd", linewidth=0.5)
    ax.set_axisbelow(True)


def application_target_time(case, byte_target):
    path = case.input_path("app")
    if path is None:
        return None
    delivered = 0
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("flow_id") != case.flow_id:
                continue
            delivered += int(row.get("payload_bytes", 0))
            if delivered >= byte_target:
                return int(row["time_ns"]) / 1e9
    return None


def save(fig, stem, args, records, details):
    args.out.mkdir(parents=True, exist_ok=True)
    for extension in ("png", "pdf"):
        path = args.out / f"{stem}.{extension}"
        fig.savefig(path, dpi=240, bbox_inches="tight", facecolor="white")
        print(path)
    plt.close(fig)
    records[stem] = details


def selected(cases, keys, role):
    output = [cases[key] for key in keys if key in cases]
    missing = [key for key in keys if key not in cases]
    if missing:
        warn(f"{role}: cases unavailable: {', '.join(missing)}")
    return output


def causal_figure(cases, args, records):
    chosen = selected(cases, args.causal, "causal figure")
    if len(chosen) != 2:
        return
    lo, hi = args.window
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 6.0), sharex=True,
                             gridspec_kw={"height_ratios": [1, 1, 1.35]})
    fig.subplots_adjust(top=0.91, bottom=0.14, left=0.15, right=0.98, hspace=0.14)
    missing_traces = []
    detailed = []
    for i, case in enumerate(chosen):
        color, style, _ = case_style(case, i)
        xs, ys = goodput_points(case, args.window)
        if not len(xs):
            warn(f"{case.key}: no receiver_application_bins; run analysis with --include-bins")
            missing_traces.append(f"{case.label}: receiver bins missing")
        else:
            axes[0].step(xs, ys, where="post", color=color, linestyle=style, label=case.label)
        xs, ys = changes(case.legacy_path("cwnd"), args.mss, args.window)
        if len(xs):
            axes[1].step(xs, ys, where="post", color=color, linestyle=style)
        else:
            missing_traces.append(f"{case.label}: cwnd missing")
        xs, ys = state_points(case, args.window)
        if len(xs):
            axes[2].step(xs, ys, where="post", color=color, linestyle=style)
        else:
            missing_traces.append(f"{case.label}: CONG trace missing")
        retx = typed_rows(case, "sender", {"RETX"}, args.window)
        retx_times = [int(r["time_ns"]) / 1e9 for r in retx if int(r.get("payload_bytes", 0)) > 0]
        axes[2].scatter(retx_times, [5] * len(retx_times), color=color,
                        marker="x" if i == 0 else "+", s=28, zorder=4)
        event = case.event(args.event)
        gaps = ((event or {}).get("gap_case_samples", {}).get(case.flow_id, []))
        accepted = [g for g in gaps if g.get("original_fill_confirmed") and
                    g.get("acceptance_observed_ns") is not None and
                    lo <= g["acceptance_observed_ns"] / 1e9 <= hi]
        # Prefer the causally relevant original accepted before needless recovery.
        relevant = [g for g in accepted if
                    g.get("classification") == "candidate_unnecessary_recovery_original_arrived"]
        example = (relevant or accepted or [None])[0]
        if i == 0 and example is not None:
            t = example["acceptance_observed_ns"] / 1e9
            axes[2].scatter([t], [5.7], color="#333333", marker="o", s=22, zorder=5)
            axes[2].annotate(f"Original accepted\n{t:.6f} s", xy=(t, 5.7),
                             xytext=(lo + 0.42 * (hi-lo), 6.2), fontsize=8,
                             arrowprops={"arrowstyle": "->", "lw": 0.65, "color": "#333333"},
                             va="bottom")
            recovery = example.get("recovery_evidence", [])
            if recovery:
                t_recovery = recovery[0]["time_ns"] / 1e9
                axes[2].annotate(f"Sender RECOVERY\n{t_recovery:.6f} s",
                                 xy=(t_recovery, 3), xytext=(lo + 0.70 * (hi-lo), 3.9),
                                 fontsize=8, va="bottom",
                                 arrowprops={"arrowstyle": "->", "lw": 0.65, "color": color})
        detailed.append({"case": case.key, "event": event, "retransmissions_in_window": len(retx_times),
                         "annotated_gap": example if i == 0 else None})
    for ax in axes:
        ax.axvline(args.event, color="#666666", linestyle=":", linewidth=0.8)
        ax.set_xlim(lo, hi)
    format_ax(axes[0], "Receiver goodput\n(Mbit/s)")
    axes[0].set_ylim(bottom=0)
    axes[0].legend(loc="upper right", frameon=False, ncol=2)
    format_ax(axes[1], f"Congestion window\n(MSS; {args.mss:g} bytes)")
    axes[1].set_ylim(bottom=0)
    format_ax(axes[2], "Sender state / events")
    axes[2].set_yticks([0, 1, 2, 3, 4, 5, 5.7],
                       ["OPEN", "DISORDER", "CWR", "RECOVERY", "LOSS", "RETX", "Original RX"])
    axes[2].set_ylim(-0.35, 7.2)
    axes[2].set_xlabel("Simulation time (s)")
    axes[0].text(args.event, 1.04, "Route update", transform=axes[0].get_xaxis_transform(),
                 ha="center", fontsize=8)
    fig.suptitle(f"TCP response near the {args.event:g} s route update", fontsize=11, y=0.985)
    bin_width = chosen[0].data.get("analysis_parameters", {}).get("bin_s", "unknown")
    footer = (f"{args.stage.capitalize()}; one simulated trace per case. Goodput uses {bin_width} s "
              "receiver application bins; state and transmission events use exact trace times.")
    if missing_traces:
        footer += "\nUnavailable: " + "; ".join(missing_traces)
    fig.text(0.15, 0.025, footer, fontsize=7.3, va="bottom", wrap=True)
    save(fig, "route_event_causal", args, records,
         {"cases": [c.key for c in chosen], "window_s": list(args.window), "details": detailed,
          "missing_traces": missing_traces})


def comparison_figure(cases, args, records):
    chosen = selected(cases, args.compare, "comparison figure")
    if len(chosen) < 2:
        return
    full = [c.flow.get("receiver_application_goodput_mbps") for c in chosen]
    events = [c.event(args.event) for c in chosen]
    event_values = [(e or {}).get("flows", {}).get(c.flow_id, {}).get("receiver_application_goodput_mbps")
                    for c, e in zip(chosen, events)]
    windows = [(e.get("window_start_s"), e.get("window_end_s")) for e in events if e]
    if len(set(windows)) > 1:
        warn("Event comparison skipped: summary windows have different bounds")
        return
    if not all(finite(v) for v in full + event_values):
        warn("Comparison skipped: receiver goodput or requested event summary missing")
        return
    duration_labels = sorted({float(c.data["duration_s"]) for c in chosen})
    if len(duration_labels) != 1:
        warn("Whole-run comparison skipped: case durations differ")
        return
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.5), sharey=True)
    fig.subplots_adjust(left=0.12, right=0.98, top=0.82, bottom=0.33, wspace=0.18)
    ylim = max(full + event_values) * 1.18
    colors = [case_style(c, i)[0] for i, c in enumerate(chosen)]
    hatches = ["", "//", "..", "xx", "\\\\"]
    for ax, values, title in zip(axes, (full, event_values),
            (f"Whole run: 0–{duration_labels[0]:g} s", f"Event window: {windows[0][0]:g}–{windows[0][1]:g} s")):
        bars = ax.bar(range(len(chosen)), values, color=colors, width=0.66,
                      edgecolor="#333333", linewidth=0.4,
                      hatch=[hatches[case_style(c, i)[2] % len(hatches)] for i, c in enumerate(chosen)])
        ax.set_xticks(range(len(chosen)), [c.label.replace(" threshold ", "\nthreshold ").replace(" guard ", "\nguard ")
                                         for c in chosen], rotation=15, ha="right", fontsize=8)
        ax.set_title(title, fontsize=9)
        ax.set_ylim(0, ylim)
        format_ax(ax, "Receiver goodput (Mbit/s)" if ax is axes[0] else "")
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, value + ylim*.02, f"{value:.3f}",
                     ha="center", fontsize=8)
    fig.suptitle("Whole-run and route-event receiver goodput", fontsize=11, y=0.975)
    lines = ["Exact means (Mbit/s)       whole run    whole Δ      event      event Δ"]
    values_output = []
    for c, a, b in zip(chosen, full, event_values):
        delta_pct = (b / event_values[0] - 1) * 100 if event_values[0] else None
        full_delta = (a / full[0] - 1) * 100 if full[0] else None
        lines.append(f"{c.label:<25} {a:9.6f} {full_delta:+8.3f}%  {b:9.6f} {delta_pct:+8.3f}%"
                     if delta_pct is not None and full_delta is not None
                     else f"{c.label:<25} {a:9.6f} undefined  {b:9.6f} undefined")
        values_output.append({"case": c.key, "whole_run_goodput_mbps": a, "event_goodput_mbps": b,
                              "event_change_vs_first_pct": delta_pct,
                              "whole_run_change_vs_first_pct": full_delta})
    fig.text(0.12, 0.11, "\n".join(lines), family="monospace", fontsize=7.2, va="bottom")
    fig.text(0.12, 0.025, f"{args.stage.capitalize()}; one trace per case, no statistical interval. "
             "All Δ values are relative to the first case.\n"
             "Both bar axes start at zero and share a scale; event gains do not represent whole-run gains.",
             fontsize=7.2, va="bottom")
    save(fig, "receiver_goodput_comparison", args, records,
         {"cases": [c.key for c in chosen], "event_time_s": args.event, "event_window_s": windows[0],
          "values": values_output})


def loss_figure(cases, args, records):
    chosen = selected(cases, args.loss, "loss figure")
    if len(chosen) < 2:
        return
    observations = []
    for case in chosen:
        distinct = {}
        for drop in case.flow.get("drop_case_samples", []):
            if args.drop_layer and drop.get("layer") not in args.drop_layer:
                continue
            if drop.get("tx_id") is None:
                continue
            identity = (drop["tx_id"], drop.get("seq"), drop.get("end_seq"))
            if identity not in distinct or drop["time_ns"] < distinct[identity]["time_ns"]:
                distinct[identity] = drop
        observations.append(list(distinct.values()))
    if not any(observations):
        warn("Loss figure skipped: no tagged drop_case_samples")
        return
    panel_count = 3 if args.loss_completion_bytes is not None else 2
    fig, axes = plt.subplots(1, panel_count, figsize=(3.7 * panel_count, 4.5))
    fig.subplots_adjust(left=0.13, right=0.98, top=0.82, bottom=0.3, wspace=0.35)
    points = []
    completions = []
    for i, (case, drops) in enumerate(zip(chosen, observations)):
        color = case_style(case, i)[0]
        for j, drop in enumerate(drops):
            # Deterministic horizontal jitter separates multiple observed losses.
            x = i + (j - (len(drops)-1)/2) * min(0.12, 0.5/max(1, len(drops)))
            retrans_delay = drop.get("retransmission_delay_s")
            resolution = drop.get("gap_resolution_delay_s")
            confirmed = bool(drop.get("accepted_fill_is_matching_retransmission"))
            if finite(retrans_delay):
                axes[0].scatter([x], [retrans_delay*1000], color=color, marker="x", s=33, zorder=3)
                if len(drops) == 1:
                    axes[0].annotate(f"{retrans_delay*1000:.2f} ms", (x, retrans_delay*1000),
                                     xytext=(0, 8), textcoords="offset points", ha="center", fontsize=7.5)
            if finite(resolution):
                axes[1].scatter([x], [resolution*1000], edgecolor=color,
                                facecolor=color if confirmed else "none", marker="o", s=33, zorder=3)
                if len(drops) == 1:
                    state = (drop.get("first_matching_recovery_state") or {}).get("state", "")
                    axes[1].annotate(f"{state}\n{resolution*1000:.2f} ms", (x, resolution*1000),
                                     xytext=(0, 8), textcoords="offset points", ha="center", fontsize=7.5)
            points.append({"case": case.key, "tx_id": drop.get("tx_id"), "drop_time_ns": drop.get("time_ns"),
                           "retransmission_delay_s": retrans_delay, "gap_resolution_delay_s": resolution,
                           "accepted_fill_is_matching_retransmission": confirmed})
        if not drops:
            for ax in axes:
                ax.text(i, 0.025, "No drop sample", transform=ax.get_xaxis_transform(), ha="center", fontsize=7)
        unmatched = sum(not finite(d.get("gap_resolution_delay_s")) for d in drops)
        if unmatched:
            axes[1].text(i, 0.98, f"{unmatched}\nno gap match", transform=axes[1].get_xaxis_transform(),
                          ha="center", va="top", fontsize=7)
        if panel_count == 3:
            completion = application_target_time(case, args.loss_completion_bytes)
            completions.append({"case": case.key, "target_bytes": args.loss_completion_bytes,
                                "receiver_target_time_s": completion})
            if completion is not None:
                axes[2].scatter([i], [completion], color=color, marker="s", s=33, zorder=3)
                axes[2].annotate(f"{completion:.6f} s", (i, completion),
                                 xytext=(0, 8), textcoords="offset points", ha="center", fontsize=7.5)
            else:
                axes[2].text(i, 0.5, "Target not observed", transform=axes[2].get_xaxis_transform(),
                              ha="center", fontsize=7)
    titles = ["Drop → first matching retransmission", "Drop → receiver sequence-gap resolution"]
    if panel_count == 3:
        titles.append(f"Receiver delivery reaches {args.loss_completion_bytes:,} bytes")
    for i, (ax, title) in enumerate(zip(axes, titles)):
        format_ax(ax, "Simulation time (s)" if i == 2 else "Delay (ms)")
        ax.set_title(title, fontsize=8.5)
        upper = ax.get_ylim()[1]
        ax.set_ylim(0, max(upper * 1.18, 1e-3))
        ax.set_xlim(-0.6, len(chosen)-0.4)
        ax.set_xticks(range(len(chosen)), [c.label for c in chosen], rotation=17, ha="right", fontsize=8)
    fig.legend(handles=[
        Line2D([], [], color="#555555", marker="o", linestyle="none", label="Accepted fill matches retransmission"),
        Line2D([], [], color="#555555", marker="o", markerfacecolor="none", linestyle="none", label="Gap resolution only")],
        fontsize=7.2, loc="lower left", bbox_to_anchor=(0.13, 0.13), ncol=2, frameon=False)
    fig.suptitle(args.loss_title, fontsize=11, y=0.975)
    layers_label = "/".join(args.drop_layer) if args.drop_layer else "all observed layers"
    fig.text(0.13, 0.025, f"{args.stage.capitalize()}; tagged drop samples from {layers_label}, one point per distinct transmission.\n"
             "Gap resolution is a repair proxy unless the accepted fill tag matches; missing delays are not plotted as zero.\n"
             "Missing gap matches do not imply unrepaired loss. Summary samples may be capped; no statistical interval is inferred.",
             fontsize=7.2, va="bottom")
    save(fig, "stable_path_loss_recovery", args, records,
         {"cases": [c.key for c in chosen], "observations": points, "application_targets": completions,
          "drop_layer_filter": args.drop_layer,
          "note": "Summary samples; unique transmission ID, sequence range deduplicates layers."})


def candidate_figure(cases, args, records):
    chosen = selected(cases, args.candidates, "candidate baseline figure")
    if len(chosen) < 2:
        return
    duration = min(float(c.data["duration_s"]) for c in chosen)
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 6.0), sharex=True)
    fig.subplots_adjust(left=0.15, right=0.98, top=0.9, bottom=0.18, hspace=0.18)
    available = {"goodput": [], "cwnd": [], "srtt": []}
    for i, case in enumerate(chosen):
        color, style, _ = case_style(case, i)
        common = {"color": color, "linestyle": style, "label": case.label}
        for ax, quantity, points in (
            (axes[0], "goodput", coarse_goodput_points(case, args.candidate_bin_s, duration)),
            (axes[1], "cwnd", changes(case.legacy_path("cwnd"), args.mss, (0, duration))),
            (axes[2], "srtt", changes(case.legacy_path("rtt"), 1e6, (0, duration))),
        ):
            xs, ys = points
            if len(xs):
                ax.step(xs, ys, where="post", **common)
                available[quantity].append(case.key)
        # A zero initialization of the RTT trace is not a measured zero RTT.
        for line in axes[2].lines[-1:]:
            if line.get_label() == case.label:
                y = np.asarray(line.get_ydata(), dtype=float)
                line.set_ydata(np.where(y > 0, y, np.nan))
    for ax, label in zip(axes, ("Receiver goodput\n(Mbit/s)", f"Congestion window\n(MSS; {args.mss:g} bytes)",
                                "Sender smoothed RTT\n(ms)")):
        format_ax(ax, label)
        ax.set_ylim(bottom=0)
        ax.set_xlim(0, duration)
    axes[0].legend(loc="upper right", ncol=min(3, len(chosen)), frameon=False)
    axes[2].set_xlabel("Simulation time (s)")
    fig.suptitle("Baseline congestion-control traces in the supplied LEO model", fontsize=11, y=0.985)
    fig.text(0.15, 0.025, f"{args.stage.capitalize()}; one trace per algorithm. Receiver goodput uses {args.candidate_bin_s:g} s bins.\n"
             "In-order application release can temporarily exceed link rate when buffered data becomes deliverable.\n"
             "RTT is the sender SRTT trace, not raw packet RTT or an isolated measurement of queueing delay.",
             fontsize=7.2, va="bottom")
    save(fig, "candidate_baseline_traces", args, records,
         {"cases": [c.key for c in chosen], "plotted_duration_s": duration,
          "requested_goodput_bin_s": args.candidate_bin_s, "available_traces": available})


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs-root", type=Path, default=Path("/tmp/cs30401-study"))
    parser.add_argument("--out", type=Path, default=Path("/work/figures"))
    parser.add_argument("--case", action="append", type=assignment, default=[], metavar="KEY=FOLDER")
    parser.add_argument("--label", action="append", type=assignment, default=[], metavar="KEY=TEXT")
    parser.add_argument("--flow-id", default="0")
    parser.add_argument("--mss", type=float, default=1380, help="MSS bytes for cwnd conversion (default: 1380)")
    parser.add_argument("--candidate-bin-s", type=float, default=1.0,
                        help="Candidate plot delivery bins; must align with source bins (default: 1 s)")
    parser.add_argument("--event", type=float, default=26.2, help="Route event in analysis windows (s)")
    parser.add_argument("--window", nargs=2, type=float, default=None, metavar=("START_S", "END_S"))
    parser.add_argument("--causal", nargs=2, default=["leo10-base", "leo10-guard20"], metavar=("BASE", "GUARD"))
    parser.add_argument("--compare", nargs="+", default=["leo10-base", "leo10-static20", "leo10-guard20"])
    parser.add_argument("--loss", nargs="+", default=["micro-loss-base", "micro-loss-static64", "micro-loss-guard64"])
    parser.add_argument("--loss-title", default="Recovery following tagged loss on a stable path")
    parser.add_argument("--drop-layer", nargs="+", help="Restrict loss points to drop trace layers, e.g. PhyRxDrop")
    parser.add_argument("--loss-completion-bytes", type=int,
                        help="Add exact receiver application byte-target time panel for finite transfers")
    parser.add_argument("--candidates", nargs="+", default=["leo10-base", "leo10-vegas", "leo10-bbr"])
    parser.add_argument("--only", nargs="+", choices=["causal", "comparison", "loss", "candidates"],
                        default=["causal", "comparison", "loss", "candidates"])
    parser.add_argument("--stage", default="initial experiment", help="Visible provenance label, e.g. preliminary or final matrix v4")
    args = parser.parse_args()
    if args.mss <= 0:
        parser.error("MSS must be positive")
    if args.candidate_bin_s <= 0:
        parser.error("Candidate bin width must be positive")
    if args.loss_completion_bytes is not None and args.loss_completion_bytes <= 0:
        parser.error("Application byte target must be positive")
    if args.window is None:
        args.window = (args.event - 0.5, args.event + 2.0)
    if args.window[0] < 0 or args.window[1] <= args.window[0]:
        parser.error("Expected 0 <= window start < end")
    return args


def main():
    args = parse_args()
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
                         "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
                         "font.family": "DejaVu Sans", "pdf.fonttype": 42, "ps.fonttype": 42,
                         "lines.linewidth": 1.1})
    paths = {p.name: p for p in args.runs_root.iterdir() if p.is_dir()} if args.runs_root.exists() else {}
    paths.update({key: Path(value) for key, value in args.case})
    labels = {**DEFAULT_LABELS, **dict(args.label)}
    requested = set(args.causal + args.compare + args.loss + args.candidates)
    cases, provenance = {}, {}
    for key in sorted(requested):
        folder = paths.get(key)
        source = folder / "study_analysis.json" if folder else None
        if source is None or not source.exists():
            continue
        data = json.loads(source.read_text())
        if args.flow_id not in data.get("flows", {}):
            warn(f"{key}: flow {args.flow_id} missing")
            continue
        cases[key] = Case(key, folder, labels.get(key, key), data, args.flow_id)
        provenance[key] = {"label": cases[key].label, "summary": str(source.resolve()),
                           "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                           "duration_s": data.get("duration_s"), "analysis_parameters": data.get("analysis_parameters"),
                           "inputs": data.get("inputs"), "limitations": data.get("limitations")}
    records = {}
    functions = {"causal": causal_figure, "comparison": comparison_figure,
                 "loss": loss_figure, "candidates": candidate_figure}
    for kind in args.only:
        functions[kind](cases, args, records)
    if not records:
        warn("No figure generated. Check case folders and summary availability.")
        return 1
    metadata = {"stage": args.stage, "flow_id": args.flow_id, "mss_bytes": args.mss,
                "sources": provenance, "figures": records}
    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out / "figure_sources.json"
    output.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
