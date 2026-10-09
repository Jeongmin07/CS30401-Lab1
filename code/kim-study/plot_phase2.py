#!/usr/bin/env python3
"""Plot phase 2 study results as IEEE single-column PNG/PDF figures.

Run inside the study container (matplotlib and numpy are installed):
  python3 /work/plot_phase2.py --out /work/figures/phase2
  python3 /work/plot_phase2.py --include-k8 --out /work/figures/phase2-with-k8

Inputs are the phase2 result table, case.json, study_analysis.json, and original
trace files.  No simulation is invoked.  Every used input is hashed.  Exempt21
means guard bypass for a KNOWN total finite transfer size <=21 MSS, rather than
a dynamic bound on flight size.  The zero timing offset comes from the actual
nominal bulk case; it is never fabricated or copied from an unrelated run.
"""

from __future__ import annotations

import argparse
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
from matplotlib.patches import Patch


MODES = ("base", "guard20", "exempt21")
LABELS = {"base": "Baseline", "guard20": "Guard K20", "exempt21": "Guard K20 + exemption"}
COLORS = {"base": "#0072B2", "guard20": "#009E73", "exempt21": "#CC79A7"}
HATCHES = {"base": "", "guard20": "//", "exempt21": ".."}


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def valid_number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


@dataclass
class Case:
    row: dict
    folder: Path
    analysis: dict
    manifest: dict
    flow_id: str

    @property
    def name(self):
        return self.row["case"]

    @property
    def flow(self):
        return self.analysis["flows"][self.flow_id]

    @property
    def parameters(self):
        return self.manifest["parameters"]

    @property
    def control(self):
        return dict(part.split("=", 1) for part in self.parameters.get("parameters", "").split(";")
                    if "=" in part)

    def completion(self):
        if self.row.get("transfer_complete") is not True:
            raise ValueError(f"{self.name}: finite application transfer is incomplete")
        timestamp = self.row.get("completion_time_s")
        if not valid_number(timestamp):
            raise ValueError(f"{self.name}: completion time missing")
        observed = self.flow.get("last_receiver_application_delivery_time_s")
        if not valid_number(observed) or abs(timestamp-observed) > 1e-8:
            raise ValueError(f"{self.name}: table completion does not match receiver summary endpoint")
        expected = self.row.get("expected_finite_bytes")
        if self.flow["counts"].get("application_delivered_bytes") != expected:
            raise ValueError(f"{self.name}: receiver delivered bytes do not match finite byte target")
        # All present cases start at zero; subtraction also keeps future runs honest.
        return timestamp - float(self.parameters.get("flow_start_s", 0))

    def event(self, time_s, bounds):
        found = [e for e in self.analysis["path_event_windows"] if abs(e["time_s"]-time_s) < 1e-8]
        if len(found) != 1:
            raise ValueError(f"{self.name}: expected exactly one summary at {time_s:g} s")
        item = found[0]
        actual = [item["window_start_s"], item["window_end_s"]]
        if any(abs(a-b) > 1e-8 for a, b in zip(actual, bounds)):
            raise ValueError(f"{self.name}: event bounds {actual} differ from required {bounds}")
        return item["flows"][self.flow_id]["receiver_application_goodput_mbps"]

    def windows(self):
        encoded = self.control.get("study_windows")
        if encoded is None:
            return []
        return [[int(value)/1e9 for value in pair.split(":")] for pair in encoded.split("|")]


class Study:
    def __init__(self, args):
        self.args = args
        self.rows = json.loads(args.results.read_text())["cases"]
        if args.sizes is None:
            args.sizes = sorted({r["nominal_mss"] for r in self.rows
                                 if r.get("family") == "finite_actual_loss"
                                 and r.get("loss_position") == "first" and r.get("mode") in MODES})
        self.cache = {}
        self.used = set()
        self.figures = {}

    def lookup(self, **criteria):
        matches = [r for r in self.rows if all(r.get(key) == value for key, value in criteria.items())]
        if len(matches) != 1:
            raise ValueError(f"Expected one case for {criteria}, found {len(matches)}")
        return self.load(matches[0])

    def load(self, row):
        name = row["case"]
        self.used.add(name)
        if name not in self.cache:
            folder = self.args.runs_root / name
            data = json.loads((folder / "study_analysis.json").read_text())
            manifest = json.loads((folder / "case.json").read_text())
            if manifest.get("status") != "complete" or manifest.get("exit_code") != 0:
                raise ValueError(f"{name}: manifest does not certify a completed run")
            if row.get("patch_sha256") != manifest.get("patch_sha256"):
                raise ValueError(f"{name}: aggregate table and manifest patch hashes differ")
            if self.args.flow_id not in data.get("flows", {}):
                raise ValueError(f"{name}: requested flow is absent")
            case = Case(row, folder, data, manifest, self.args.flow_id)
            if row.get("distinct_tagged_drops") != case.flow.get("distinct_tagged_transmissions_dropped"):
                raise ValueError(f"{name}: aggregate and summary drop counts differ")
            nominal = row.get("nominal_mss")
            if nominal is not None and row.get("expected_finite_bytes") != nominal * self.args.mss:
                raise ValueError(f"{name}: nominal MSS and finite byte target disagree")
            self.cache[name] = case
        return self.cache[name]

    def figure(self, title, legend=True, height=3.35):
        fig, ax = plt.subplots(figsize=(self.args.width, height))
        fig.subplots_adjust(left=0.22, right=0.975, top=0.72 if legend else 0.86, bottom=0.26)
        fig.text(0.51, 0.985, title, ha="center", va="top", fontsize=self.args.fontsize + 0.3)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", color="#dddddd", linewidth=0.45)
        ax.set_axisbelow(True)
        return fig, ax

    def legend(self, fig, extra=None):
        handles = [Patch(facecolor=COLORS[mode], edgecolor="#333333", hatch=HATCHES[mode],
                         linewidth=0.4, label=LABELS[mode]) for mode in MODES]
        if extra:
            handles.append(extra)
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.53, 0.945),
                   frameon=False, fontsize=self.args.fontsize-0.5, ncol=1,
                   labelspacing=0.2, handlelength=1.8)

    def footer(self, fig, text):
        # Keep annotation lines short so the PDF remains exactly one column wide.
        fig.text(0.22, 0.015, text, fontsize=self.args.fontsize-0.5, va="bottom", linespacing=1.12)

    def save(self, fig, name, caption, values):
        self.args.out.mkdir(parents=True, exist_ok=True)
        files = []
        for ext in ("png", "pdf"):
            path = self.args.out / f"{name}.{ext}"
            # Do not use tight bounding boxes: the requested IEEE column width
            # must remain exactly 3.45 inches, with labels laid out inside it.
            fig.savefig(path, dpi=300, facecolor="white")
            files.append({"path": str(path.resolve()), "sha256": digest(path), "size_bytes": path.stat().st_size})
            print(path)
        self.figures[name] = {"width_in": float(fig.get_figwidth()), "height_in": float(fig.get_figheight()),
                              "caption": caption, "values": values, "files": files}
        plt.close(fig)

    def provenance(self):
        cases = {}
        for name in sorted(self.used):
            case = self.cache[name]
            sources = []
            paths = [case.folder / "case.json", case.folder / "study_analysis.json", case.folder / "config_ns3.properties"]
            schedule = case.folder / "schedule.csv"
            if schedule.exists():
                paths.append(schedule)
            for item in case.analysis.get("inputs", []):
                original = Path(item["path"])
                fallback = case.folder / "logs_ns3" / original.name
                path = original if original.exists() else fallback
                if not path.exists():
                    raise ValueError(f"{name}: source trace missing: {path}")
                paths.append(path)
            for path in dict.fromkeys(paths):
                sources.append({"path": str(path.resolve()), "size_bytes": path.stat().st_size, "sha256": digest(path)})
            cases[name] = {"result_row": case.row, "actual_parameters": case.parameters,
                           "actual_windows_s": case.windows(), "command": case.manifest.get("command"),
                           "official_image_digest": case.manifest.get("official_image_digest"),
                           "patch_sha256": case.manifest.get("patch_sha256"),
                           "binary_sha256": case.manifest.get("binary_sha256"), "sources": sources,
                           "analysis_parameters": case.analysis.get("analysis_parameters"),
                           "analysis_limitations": case.analysis.get("limitations")}
        inputs = [{"path": str(self.args.results.resolve()), "sha256": digest(self.args.results)}]
        csv_path = self.args.results.with_suffix(".csv")
        if csv_path.exists():
            inputs.append({"path": str(csv_path.resolve()), "sha256": digest(csv_path)})
        script = Path(__file__).resolve()
        return {"schema_version": 1, "script": {"path": str(script), "sha256": digest(script)},
                "command": [sys.executable, *sys.argv], "dataset_inputs": inputs,
                "dataset_case_count": len(self.rows), "used_case_count": len(cases),
                "flow_id": self.args.flow_id, "mss_bytes": self.args.mss,
                "font_size_pt": self.args.fontsize, "figure_width_in": self.args.width,
                "statistical_scope": "One deterministic trace per configuration; no confidence interval.",
                "cases": cases, "figures": self.figures}


def grouped_fct(study, family, categories, category_key, criteria, title, name, footer, caption, add_k8=False):
    fig, ax = study.figure(title, height=3.6 if add_k8 else 3.35)
    if add_k8:
        fig.subplots_adjust(top=0.67)
    x = np.arange(len(categories))
    width = 0.24
    values = []
    maximum = 0
    for index, mode in enumerate(MODES):
        cases = [study.lookup(family=family, mode=mode, **criteria, **{category_key: category}) for category in categories]
        fcts = [case.completion() for case in cases]
        positions = x + (index-1)*width
        ax.bar(positions, fcts, width=width*0.94, facecolor=COLORS[mode], edgecolor="#333333",
               hatch=HATCHES[mode], linewidth=0.4)
        maximum = max(maximum, *fcts)
        for case, category, fct in zip(cases, categories, fcts):
            values.append({"case": case.name, "mode": mode, "category": category,
                           "completion_time_s": fct, "drops": case.row["distinct_tagged_drops"],
                           "short_flow_bypass": case.row["short_flow_bypass"],
                           "loss_state_entries": case.row["loss_state_entries"]})
    extra = None
    if add_k8:
        case = study.lookup(family="finite_actual_loss", nominal_mss=20, mode="guard8", loss_position="first")
        value = case.completion()
        ax.scatter([categories.index(20)], [value], marker="D", color="#222222", s=18, zorder=5)
        extra = Line2D([], [], marker="D", color="#222222", linestyle="none", markersize=4,
                       label="K8: 20-MSS test only")
        values.append({"case": case.name, "mode": "guard8", "category": 20, "completion_time_s": value})
    study.legend(fig, extra)
    ax.set_xticks(x, [str(value).capitalize() for value in categories])
    ax.set_xlim(-0.65, len(categories)-0.35)
    ax.set_ylim(0, maximum*1.24)
    ax.set_ylabel("Flow completion time (s)")
    ax.set_xlabel("Transfer size (MSS)" if category_key == "nominal_mss" else "Lost segment position")
    study.footer(fig, footer)
    study.save(fig, name, caption, values)


def first_loss(study):
    cases = [study.lookup(family="finite_actual_loss", nominal_mss=size, mode=mode, loss_position="first")
             for size in study.args.sizes for mode in MODES]
    for case in cases:
        if case.parameters.get("loss_seq") != 1 or case.row["distinct_tagged_drops"] != 1:
            raise ValueError(f"{case.name}: first-loss figure requires one drop at sequence 1")
    grouped_fct(study, "finite_actual_loss", study.args.sizes, "nominal_mss", {"loss_position": "first"},
                "Finite transfer with first-segment loss", "finite_size_first_loss",
                "Exemption: known finite size ≤21 MSS.\nAt 3 MSS, baseline also enters timeout.\nOne drop; one trace per configuration.",
                "Receiver application completion time from flow start, with exactly one first-segment loss on the stable micro path. "
                "Categorical transfer sizes are equally spaced. The exemption bypasses the guard for known total finite length ≤21 MSS. "
                "Three-MSS baseline loss also times out; this policy does not solve every short-flow loss. "
                "An optional K8 point applies only to the measured 20-MSS case.", study.args.include_k8)


def loss_position(study):
    grouped_fct(study, "finite_actual_loss", ["first", "middle", "last"], "loss_position", {"nominal_mss": 20},
                "Loss position in a 20-MSS transfer", "finite20_loss_position",
                "Exemption: known finite size ≤21 MSS.\nLast-segment loss times out in all modes.\nOne drop; one trace per configuration.",
                "Twenty-MSS finite transfer on the stable micro path with one genuine first-, middle- or last-segment loss. "
                "Completion is measured at receiver application delivery from flow start. Exemption matches the baseline for first/middle loss "
                "but last-segment loss still requires the timeout path in every tested mode.")


def notification(study):
    nominal = study.lookup(family="bulk_leo", mode="exempt21")
    baseline = study.lookup(family="bulk_leo", mode="base")
    windows = nominal.windows()
    if not windows:
        raise ValueError("Nominal bulk case has no actual protection windows")
    points = []
    for row in study.rows:
        if row.get("family") == "notification_error":
            case = study.load(row)
            offset = int(row["notice_window_offset_ms"])
            actual = case.windows()
            if len(actual) != len(windows) or any(abs(a-b-offset/1000) > 1e-8
                for pair, nominal_pair in zip(actual, windows) for a, b in zip(pair, nominal_pair)):
                raise ValueError(f"{case.name}: offset does not shift both nominal window bounds")
            points.append((offset, case))
    if any(offset == 0 for offset, _ in points):
        raise ValueError("Zero-offset notification case duplicates the nominal bulk control")
    points.append((0, nominal))
    points.sort(key=lambda item: item[0])
    required = [-200, -100, 0, 100, 200, 250, 300]
    if [item[0] for item in points] != required:
        raise ValueError("Notification figure requires exactly the seven requested tested offsets")
    whole_base = baseline.flow["receiver_application_goodput_mbps"]
    event_base = baseline.event(study.args.event_s, study.args.event_window)
    values = []
    for offset, case in points:
        if case.analysis["duration_s"] != baseline.analysis["duration_s"]:
            raise ValueError(f"{case.name}: whole-run durations differ")
        whole = case.flow["receiver_application_goodput_mbps"]
        event = case.event(study.args.event_s, study.args.event_window)
        values.append({"case": case.name, "window_offset_ms": offset, "whole_run_goodput_mbps": whole,
                       "event_goodput_mbps": event, "whole_run_change_pct": (whole/whole_base-1)*100,
                       "event_change_pct": (event/event_base-1)*100, "actual_windows_s": case.windows()})
    fig, ax = study.figure("Timing of the protection window", height=3.7)
    fig.subplots_adjust(top=0.77, bottom=0.35)
    x = [v["window_offset_ms"] for v in values]
    ax.scatter(x, [v["whole_run_change_pct"] for v in values], color=COLORS["base"], marker="o", s=20,
               label=f"Whole run (0–{baseline.analysis['duration_s']:g} s)", zorder=4, clip_on=False)
    ax.scatter(x, [v["event_change_pct"] for v in values], edgecolor=COLORS["guard20"], facecolor="none",
               marker="s", s=28, label=f"Event ({study.args.event_window[0]:g}–{study.args.event_window[1]:g} s)",
               zorder=5, clip_on=False)
    # Points only: do not imply that untested offsets were measured/interpolated.
    fig.legend(loc="upper center", bbox_to_anchor=(0.55, 0.945), frameon=False,
               fontsize=study.args.fontsize-0.5, ncol=1, labelspacing=0.3)
    ax.set_xticks(x, [f"{offset:+d}" if offset else "0" for offset in x], rotation=45, ha="right")
    ax.set_xlim(min(x)-40, max(x)+30)
    maximum = max(v[k] for v in values for k in ("whole_run_change_pct", "event_change_pct"))
    minimum = min(v[k] for v in values for k in ("whole_run_change_pct", "event_change_pct"))
    ax.set_ylim(min(0, minimum*1.1), max(0.1, maximum*1.15))
    ax.set_ylabel("Receiver goodput change\nvs baseline (%)")
    ax.set_xlabel("Protection-window offset (ms)\nrelative to the nominal window")
    study.footer(fig, f"Nominal first window: {windows[0][0]:g}–{windows[0][1]:g} s.\n"
                 f"Baseline Mbit/s: whole {whole_base:.6f};\nevent {event_base:.6f}. Tested offsets only.")
    study.save(fig, "protection_window_offset",
               "Baseline-relative receiver goodput changes for shifts of both protection-window bounds. "
               "Offsets are not notification-arrival times; the physical route event remains at 26.2 s. "
               "Every event metric uses the same 25.7–28.2 s analysis window. Both metrics share the same zero-based percentage axis. "
               "The 0-ms point is the independently simulated nominal exemption-policy bulk case. Only tested offsets are plotted.",
               {"baseline_case": baseline.name, "nominal_case": nominal.name,
                "whole_run_baseline_mbps": whole_base, "event_baseline_mbps": event_base,
                "event_window_s": study.args.event_window, "points": values})


def delay_step(study):
    fig, ax = study.figure("Delay decrease: matched 80-MSS transfers")
    categories = (("finite_no_loss", "Stable delay"), ("finite_delay_step", "Delay decrease"))
    x = np.arange(len(categories))
    width = 0.24
    values = []
    maximum = 0
    actual_step = None
    for index, mode in enumerate(MODES):
        stable, step = [study.lookup(family=family, nominal_mss=80, mode=mode)
                        for family, _ in categories]
        # The matched control removes the propagation decrease. Validate the
        # remaining relevant topology/transport/workload settings from manifests.
        keys = ("kind", "cc", "rate", "queue", "duration", "before_ms", "loss_s",
                "loss_seq", "initial_ssthresh_pkts", "max_bytes", "flow_start_s", "parameters")
        if any(stable.parameters.get(key) != step.parameters.get(key) for key in keys):
            raise ValueError(f"{mode}: stable and delay-step parameters are not matched")
        if stable.parameters["before_ms"] != stable.parameters["after_ms"]:
            raise ValueError(f"{stable.name}: stable control changes propagation")
        if step.parameters["after_ms"] >= step.parameters["before_ms"]:
            raise ValueError(f"{step.name}: expected a propagation decrease")
        this_step = [step.parameters[key] for key in ("before_ms", "after_ms", "event_s")]
        if actual_step is not None and actual_step != this_step:
            raise ValueError("Delay-step parameters differ between transport modes")
        actual_step = this_step
        cases = (stable, step)
        if any(case.row["distinct_tagged_drops"] != 0 for case in cases):
            raise ValueError("Delay-step/control figure requires zero observed tagged drops")
        fcts = [case.completion() for case in cases]
        ax.bar(x + (index-1)*width, fcts, width=width*0.94, facecolor=COLORS[mode],
               edgecolor="#333333", hatch=HATCHES[mode], linewidth=0.4)
        maximum = max(maximum, *fcts)
        for case, (_, category), fct in zip(cases, categories, fcts):
            values.append({"case": case.name, "mode": mode, "category": category,
                           "nominal_mss": 80, "completion_time_s": fct,
                           "drops": case.row["distinct_tagged_drops"],
                           "short_flow_bypass": case.row["short_flow_bypass"],
                           "loss_state_entries": case.row["loss_state_entries"]})
    study.legend(fig)
    ax.set_xticks(x, [category for _, category in categories])
    ax.set_xlim(-0.65, len(categories)-0.35)
    ax.set_ylim(0, maximum*1.24)
    ax.set_ylabel("Flow completion time (s)")
    ax.set_xlabel("Propagation condition")
    before_ms, after_ms, event_s = actual_step
    study.footer(fig, f"Decrease: {before_ms:g}→{after_ms:g} ms at {event_s:g} s.\n"
                 f"Stable control: {before_ms:g} ms throughout.\n"
                 "One-way delay; zero tagged drops in all six.")
    study.save(fig, "finite_delay_step",
               "Matched 80-MSS finite-transfer completion times from flow start for a stable propagation control and a delay decrease. "
               f"One-way propagation changes from {before_ms:g} to {after_ms:g} ms at {event_s:g} s in the stepped cases; "
               f"the control retains {before_ms:g} ms. Remaining relevant parameters match within each mode, including guard windows. "
               "All six cases record zero tagged drops. The known-total-size exemption does not apply at 80 MSS. "
               "Values are single deterministic traces, with exact values and parameters in the source manifest.", values)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=Path("/work/phase2_results.json"))
    parser.add_argument("--runs-root", type=Path, default=Path("/tmp/cs30401-study"))
    parser.add_argument("--out", type=Path, default=Path("/work/figures/phase2"))
    parser.add_argument("--flow-id", default="0")
    parser.add_argument("--mss", type=int, default=1380)
    parser.add_argument("--width", type=float, default=3.45, help="Final PNG/PDF width in inches (default: one IEEE column)")
    parser.add_argument("--fontsize", type=float, default=8.5)
    parser.add_argument("--sizes", nargs="+", type=int,
                        help="First-loss sizes; default: all measured first-loss sizes, including 21 when available")
    parser.add_argument("--include-k8", action="store_true", help="Include the sole measured K8 point at 20 MSS")
    parser.add_argument("--event-s", type=float, default=26.2)
    parser.add_argument("--event-window", nargs=2, type=float, default=[25.7, 28.2])
    parser.add_argument("--only", nargs="+", choices=["size", "position", "notification", "step"],
                        default=["size", "position", "notification", "step"])
    args = parser.parse_args()
    if args.width <= 0 or args.fontsize <= 0 or args.mss <= 0:
        parser.error("Width, font size and MSS must be positive")
    return args


def main():
    args = parse_args()
    plt.rcParams.update({"font.family": "DejaVu Serif", "font.size": args.fontsize,
                         "axes.labelsize": args.fontsize, "xtick.labelsize": args.fontsize-0.5,
                         "ytick.labelsize": args.fontsize-0.5, "pdf.fonttype": 42, "ps.fonttype": 42,
                         "axes.linewidth": 0.6})
    study = Study(args)
    functions = {"size": first_loss, "position": loss_position, "notification": notification, "step": delay_step}
    for name in args.only:
        functions[name](study)
    print("Hashing the raw sources used by these figures...", flush=True)
    metadata = study.provenance()
    path = args.out / "figure_sources.json"
    path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    print(path)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
