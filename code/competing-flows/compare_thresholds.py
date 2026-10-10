"""Compare validated two-flow K3/DD, K20 and K8 compact exports; stdlib only.

Inputs may be export directories containing ``cases/`` or the case directories
themselves. Case names do not select conditions: schedule/config evidence does.
This script reads no raw trace and does not run simulations or the analyzer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


FLOW_IDS = ("0", "1")
SCENARIOS = {0: "same-start", 10_000_000_000: "join10"}
MODES = ("DD", "GD", "DG", "GG")
WINDOWS = ("whole", "common-active", "steady", "event26", "event75")
HASH_FIELDS = (
    "patch_sha256", "binary_sha256", "runner_sha256", "make_run_sha256",
    "official_image_digest", "config_ns3.properties_sha256",
)
ANALYSIS_HASH_FIELDS = ("analyzer_sha256", "exporter_sha256", "path_truth_sha256")
COUNTER_MAP = {
    "retransmission_rows": "official_retransmission_rows",
    "recovery_entries": "recovery_state_entries",
    "loss_entries": "loss_state_entries",
}


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def count(value, label):
    require(type(value) is int and value >= 0, f"Invalid nonnegative count: {label}")
    return value


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value), f"Invalid number: {label}")
    return value


def near(actual, expected, label):
    if expected is None:
        require(actual is None, f"Expected null: {label}")
    else:
        require(math.isclose(number(actual, label), expected, rel_tol=1e-10, abs_tol=1e-12),
                f"Derived value mismatch: {label}: {actual} != {expected}")


def jain(values):
    squares = sum(value * value for value in values)
    return sum(values) ** 2 / (len(values) * squares) if squares else None


def properties(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        require(key not in result, f"Duplicate property {key} in {path}")
        result[key] = value
    return result


def controls(text):
    if not text:
        return None
    result = {}
    for token in text.split(";"):
        key, value = token.split("=", 1)
        require(key not in result, f"Duplicate flow control {key}")
        result[key] = value
    require(set(result) == {"study_threshold", "study_windows"},
            "Only threshold and windows may differ; exemptions/other controls are not matched")
    threshold = int(result["study_threshold"])
    windows = [tuple(map(int, part.split(":"))) for part in result["study_windows"].split("|")]
    require(all(len(pair) == 2 and 0 <= pair[0] < pair[1] for pair in windows), "Invalid requested guard windows")
    require(all(left[1] <= right[0] for left, right in zip(windows, windows[1:])), "Overlapping guard windows")
    return {"threshold": threshold, "windows": windows}


def load_case(directory, threshold):
    paths = {name: directory / name for name in (
        "summary.json", "case.json", "config_ns3.properties", "schedule.csv")}
    require(all(path.is_file() for path in paths.values()), f"Missing compact input in {directory}")
    summary = json.loads(paths["summary.json"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["case.json"].read_text(encoding="utf-8"))
    config = properties(paths["config_ns3.properties"])
    require(manifest["status"] == "complete" and manifest["exit_code"] == 0,
            f"Incomplete simulation: {directory}")
    require(summary["case"] == manifest["case"] == directory.name, "Case labels disagree")
    require(summary["source_commit"] == manifest["source_commit"], "Source revisions disagree")
    for filename in ("config_ns3.properties", "schedule.csv"):
        require(digest(paths[filename]) == manifest[f"{filename}_sha256"], f"Input hash mismatch: {paths[filename]}")
    with paths["schedule.csv"].open(newline="", encoding="utf-8") as source:
        schedule = list(csv.reader(source))
    require(len(schedule) == 2 and all(len(row) == 7 and row[6] == "" for row in schedule),
            "Expected two seven-column schedule rows with empty metadata")
    require([row[0] for row in schedule] == list(FLOW_IDS), "Expected flow IDs 0,1")
    starts = [int(row[4]) for row in schedule]
    require(starts[0] == 0 and starts[1] in SCENARIOS, "Expected starts 0/0 or 0/10 seconds")
    duration = int(config["simulation_end_time_ns"])
    require(duration == 200_000_000_000, "This comparison targets the declared 200-second cases")
    require(config["tcp_socket_type"] == "TcpCubic" and config["tcp_enable_pacing"] == "false",
            "Expected unpaced CUBIC")
    require(set(summary["flows"]) == set(FLOW_IDS), "Expected exactly two analyzed flows")
    guard_controls = [controls(row[5]) for row in schedule]
    mode = "".join("G" if control else "D" for control in guard_controls)
    require(len(manifest["flows"]) == 2, "Manifest must describe two flows")
    for fid, row, control, flow_manifest in zip(FLOW_IDS, schedule, guard_controls, manifest["flows"]):
        require([int(value) for value in row[:5]] == [
            flow_manifest[key] for key in ("flow_id", "source_node", "destination_node", "size_bytes", "start_ns")],
            "Schedule and manifest flows disagree")
        require(flow_manifest["additional_parameters"] == row[5] and flow_manifest["role"] == mode[int(fid)],
                "Schedule and manifest controls disagree")
        require([int(row[1]), int(row[2]), int(row[3])] == [1584, 1585, 100_000_000_000],
                "Expected same-direction Seoul-to-London 100-GB flows")
        validation = summary["guard_validation"][fid]
        flow = summary["flows"][fid]
        require(validation["matched"] is True and validation["initial_k"] == flow["initial_retransmission_threshold"] == 3,
                "Expected validated initial K3")
        expected = [[left, threshold] for left, _ in control["windows"]] if control else []
        require(validation["expected_sets"] == validation["observed_sets"] == expected,
                "Guard activation evidence differs from requested threshold/windows")
        require(control is None or control["threshold"] == threshold, f"Expected K{threshold} guard in {directory}")
        require(flow["unfinished_protection_start_ns"] is None, "Cannot silently compare unfinished guard intervals")
        actual = flow["protection_intervals"]
        requested = control["windows"] if control else []
        require(len(actual) == len(requested), "Actual and requested interval counts differ")
        for index, (interval, (left, right)) in enumerate(zip(actual, requested)):
            require(interval["start_ns"] == left and right <= interval["end_ns"] <= duration,
                    "Unexpected actual guard interval")
            require(index + 1 == len(requested) or interval["end_ns"] <= requested[index + 1][0],
                    "Actual guard intervals overlap")
            near(interval["duration_s"], (interval["end_ns"] - left) / 1e9, "guard duration")
        count(flow["restore_deferrals"], "restore deferrals")
        count(flow["restore_deadlines_missed"], "restore deadline misses")
    connections = summary["connection_validation"]
    require(len(connections) == 2 and {item["flow_id"] for item in connections} == set(FLOW_IDS),
            "Expected separately validated receiver connections")
    require(len({(item["node"], item["local_port"], item["connection_id"]) for item in connections}) == 2,
            "Receiver connection identities are not separate")
    require(len({(item["peer_ip"], item["peer_port"]) for item in connections}) == 2,
            "Sender socket identities are not separate")
    windows = {row["window"]: row for row in summary["windows"]}
    require(len(summary["windows"]) == len(windows) and set(windows) == set(WINDOWS), "Expected five unique matched windows")
    expected_windows = {"whole": (0, duration), "common-active": (max(starts), duration),
                        "steady": (20_000_000_000, duration),
                        "event26": (25_700_000_000, 28_200_000_000),
                        "event75": (74_500_000_000, 77_000_000_000)}
    for name, row in windows.items():
        left, right = expected_windows[name]
        require(round(row["start_s"] * 1e9) == left and round(row["end_s"] * 1e9) == right,
                f"Window bounds differ: {directory}/{name}")
        require(row["case"] == directory.name and [row["guard0"], row["guard1"]] == [bool(x) for x in guard_controls],
                "Window metadata differs from schedule")
        require([round(row[f"start{fid}_s"] * 1e9) for fid in FLOW_IDS] == starts, "Window starts differ")
        values = [count(row[f"flow{fid}_bytes"], f"{name} flow{fid} bytes") for fid in FLOW_IDS]
        total = sum(values)
        rates = [value * 8 / ((right-left) / 1e9) / 1e6 for value in values]
        near(row["total_goodput_mbps"], sum(rates), "aggregate goodput")
        near(row["jain_index"], jain(values), "Jain index")
        for fid, value, rate in zip(FLOW_IDS, values, rates):
            near(row[f"flow{fid}_goodput_mbps"], rate, "flow goodput")
            near(row[f"flow{fid}_share"], value / total if total else None, "flow share")
            for counter in COUNTER_MAP:
                count(row[f"flow{fid}_{counter}"], counter)
    for fid in FLOW_IDS:
        counts = summary["flows"][fid]["counts"]
        delivered = count(counts.get("application_delivered_bytes", 0), "application bytes")
        require(windows["whole"][f"flow{fid}_bytes"] == delivered, "Whole-run delivery disagrees")
        require(next(item["delivered_bytes"] for item in connections if item["flow_id"] == fid) == delivered,
                "Connection delivered bytes disagree")
        for counter, analyzed in COUNTER_MAP.items():
            require(windows["whole"][f"flow{fid}_{counter}"] == count(counts.get(analyzed, 0), analyzed),
                    "Whole-run event counters disagree")
        wire = count(counts.get("wire_unique_sequence_bytes", 0), "wire unique bytes")
        payload = count(counts.get("wire_payload_rx_bytes", 0), "wire payload bytes")
        require(delivered <= wire <= payload, "Impossible wire/app byte accounting")
    return {"directory": directory, "summary": summary, "manifest": manifest, "config": config,
            "scenario": SCENARIOS[starts[1]], "mode": mode, "threshold": 3 if mode == "DD" else threshold,
            "policy": "K3" if mode == "DD" else f"K{threshold}", "starts": starts,
            "controls": guard_controls, "windows": windows,
            "input_hashes": [{"file": name, "sha256": digest(path), "bytes": path.stat().st_size}
                             for name, path in paths.items()]}


def read_root(root, threshold, expected_modes):
    directory = root / "cases" if (root / "cases").is_dir() else root
    require(directory.is_dir(), f"Missing case root: {root}")
    results = {}
    for path in sorted(directory.iterdir()):
        if not path.is_dir() or not (path / "summary.json").is_file():
            continue
        case = load_case(path, threshold)
        key = (case["scenario"], case["mode"])
        require(key not in results, f"Duplicate condition: {key} in {directory}")
        results[key] = case
    expected = {(scenario, mode) for scenario in SCENARIOS.values() for mode in expected_modes}
    require(set(results) == expected, f"Condition set differs: missing {expected-set(results)}, extra {set(results)-expected}")
    return results


def case_labels(case):
    return {key: case[key] for key in ("scenario", "policy", "mode", "threshold")} | {"case": case["summary"]["case"]}


def metrics_for_window(case, window):
    row = case["windows"][window]
    labels = case_labels(case) | {"window": window, "start_s": row["start_s"], "end_s": row["end_s"]}
    records = []
    for fid in FLOW_IDS:
        for suffix, metric, unit in (("bytes", "application_bytes", "B"), ("goodput_mbps", "goodput", "Mbit/s"),
                                     ("share", "delivery_share", "fraction"),
                                     ("retransmission_rows", "retransmission_rows", "rows"),
                                     ("recovery_entries", "recovery_entries", "entries"),
                                     ("loss_entries", "loss_entries", "entries")):
            records.append(labels | {"scope": f"flow{fid}", "metric": metric,
                                     "value": row[f"flow{fid}_{suffix}"], "unit": unit})
    aggregate = {"application_bytes": (sum(row[f"flow{fid}_bytes"] for fid in FLOW_IDS), "B"),
                 "goodput": (row["total_goodput_mbps"], "Mbit/s"), "jain_index": (row["jain_index"], "index")}
    aggregate.update({counter: (sum(row[f"flow{fid}_{counter}"] for fid in FLOW_IDS),
                               "rows" if counter == "retransmission_rows" else "entries") for counter in COUNTER_MAP})
    records.extend(labels | {"scope": "all", "metric": metric, "value": value, "unit": unit}
                   for metric, (value, unit) in aggregate.items())
    return records


def terminal_rows(case):
    records = []
    for fid in FLOW_IDS:
        flow = case["summary"]["flows"][fid]
        counts = flow["counts"]
        application = counts.get("application_delivered_bytes", 0)
        wire = counts.get("wire_unique_sequence_bytes", 0)
        payload = counts.get("wire_payload_rx_bytes", 0)
        records.append(case_labels(case) | {"scope": f"flow{fid}", "at_s": 200.0,
            "application_bytes": application, "wire_unique_bytes": wire, "wire_payload_bytes": payload,
            "wire_unique_minus_app_bytes": wire-application, "duplicate_wire_payload_bytes": payload-wire,
            "tagged_transmissions_dropped": count(flow["distinct_tagged_transmissions_dropped"], "tagged drops"),
            "restore_deferrals": flow["restore_deferrals"], "restore_deadlines_missed": flow["restore_deadlines_missed"]})
    aggregate = case_labels(case) | {"scope": "all", "at_s": 200.0}
    aggregate.update({key: sum(row[key] for row in records) for key in records[0]
                      if key not in case_labels(case) and key not in ("scope", "at_s")})
    return records + [aggregate]


def guard_rows(case):
    records = []
    for fid in FLOW_IDS:
        control = case["controls"][int(fid)]
        if not control:
            continue
        for index, (requested, actual) in enumerate(zip(control["windows"], case["summary"]["flows"][fid]["protection_intervals"])):
            left, right = requested
            records.append(case_labels(case) | {"scope": f"flow{fid}", "interval_index": index,
                "requested_start_ns": left, "requested_end_ns": right,
                "actual_start_ns": actual["start_ns"], "actual_end_ns": actual["end_ns"],
                "actual_duration_s": actual["duration_s"], "restore_overhang_ns": actual["end_ns"]-right})
    return records


def write_csv(path, rows):
    require(bool(rows), f"No rows for {path.name}")
    with path.open("x", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def compare(baseline, k8):
    cases = list(baseline.values()) + list(k8.values())
    reference = cases[0]
    for case in cases:
        for key in HASH_FIELDS:
            require(case["manifest"][key] == reference["manifest"][key], f"Simulation provenance differs: {key}")
        for key in ANALYSIS_HASH_FIELDS:
            require(case["summary"][key] == reference["summary"][key], f"Analysis provenance differs: {key}")
        require(case["config"] == reference["config"], "Actual configuration differs")
    for key, case in k8.items():
        counterpart = baseline[key]
        require(case["starts"] == counterpart["starts"], "Matched starts differ")
        for left, right in zip(case["controls"], counterpart["controls"]):
            require((left is None) == (right is None), "Matched guard roles differ")
            require(left is None or left["windows"] == right["windows"], "K8 and K20 requested windows differ")
    ordered = sorted(cases, key=lambda case: (list(SCENARIOS.values()).index(case["scenario"]),
                                             MODES.index(case["mode"]), case["threshold"]))
    windows, metrics, terminal, guards, inputs = [], [], [], [], []
    by_condition = {}
    for case in ordered:
        key = (case["scenario"], case["policy"], case["mode"])
        by_condition[key] = case
        for window in WINDOWS:
            original = case["windows"][window]
            windows.append(case_labels(case) | {k: value for k, value in original.items() if k != "case"})
            metrics.extend(metrics_for_window(case, window))
        terminal.extend(terminal_rows(case))
        guards.extend(guard_rows(case))
        inputs.append(case_labels(case) | {"directory": str(case["directory"]),
            "source_commit": case["manifest"]["source_commit"], "files": case["input_hashes"],
            "analysis_sha256": case["summary"]["analysis_sha256"],
            "recorded_raw_input_count": len(case["summary"]["raw_inputs"]),
            "guard_validation": case["summary"]["guard_validation"],
            "drop_rows_without_usable_transmission_tag": case["summary"]["drop_rows_without_usable_transmission_tag"]})
    contrasts = []
    for scenario in SCENARIOS.values():
        dd = by_condition[(scenario, "K3", "DD")]
        for mode in MODES[1:]:
            high = by_condition[(scenario, "K20", mode)]
            low = by_condition[(scenario, "K8", mode)]
            for treatment, control in ((high, dd), (low, dd), (low, high)):
                for window in WINDOWS:
                    treatment_metrics = metrics_for_window(treatment, window)
                    control_metrics = metrics_for_window(control, window)
                    for actual, original in zip(treatment_metrics, control_metrics):
                        require((actual["scope"], actual["metric"], actual["start_s"], actual["end_s"])
                                == (original["scope"], original["metric"], original["start_s"], original["end_s"]),
                                "Contrast intervals/metrics do not match")
                        delta = actual["value"]-original["value"] if actual["value"] is not None and original["value"] is not None else None
                        percent = delta / original["value"] * 100 if delta is not None and original["value"] != 0 else None
                        contrasts.append({"scenario": scenario, "mode": mode, "policy": treatment["policy"],
                            "case": treatment["summary"]["case"], "reference_policy": control["policy"],
                            "reference_mode": control["mode"], "reference_case": control["summary"]["case"],
                            "window": window, "start_s": actual["start_s"], "end_s": actual["end_s"],
                            "scope": actual["scope"], "metric": actual["metric"], "unit": actual["unit"],
                            "value": actual["value"], "reference_value": original["value"],
                            "delta": delta, "percent_change": percent})
    for row in terminal:
        labels = {key: row[key] for key in case_labels(ordered[0])}
        for metric in ("application_bytes", "wire_unique_bytes", "wire_payload_bytes", "wire_unique_minus_app_bytes",
                       "duplicate_wire_payload_bytes", "tagged_transmissions_dropped", "restore_deferrals", "restore_deadlines_missed"):
            metrics.append(labels | {"window": "terminal", "start_s": None, "end_s": row["at_s"], "scope": row["scope"],
                "metric": metric, "value": row[metric], "unit": "B" if metric.endswith("bytes") else "count"})
    for row in guards:
        labels = {key: row[key] for key in case_labels(ordered[0])}
        for metric, unit in (("actual_duration_s", "s"), ("restore_overhang_ns", "ns")):
            metrics.append(labels | {"window": f"guard-{row['interval_index']}", "start_s": row["actual_start_ns"] / 1e9,
                "end_s": row["actual_end_ns"] / 1e9, "scope": row["scope"], "metric": metric, "value": row[metric], "unit": unit})
    return {"schema_version": 1, "script_sha256": digest(Path(__file__)),
        "matched_provenance": {key: reference["manifest"][key] for key in HASH_FIELDS} | {
            key: reference["summary"][key] for key in ANALYSIS_HASH_FIELDS},
        "inputs": inputs, "windows": windows, "metrics": metrics, "contrasts": contrasts,
        "terminal": terminal, "guard_intervals": guards,
        "method": {
            "matching": "Two starts (0/0,0/10), same direction/size/config/binary/patch/image/analyzer; K8 vs K20 differs only in guard threshold.",
            "windows": "Half-open [start,end) intervals with identical two-flow denominator; common-active begins at the later scheduled start.",
            "application": "Unique ordered per-connection application payload from the previously validated compact export.",
            "jain": "Two delivered byte totals over the same window; null when both are zero; identical to using goodput with a shared denominator.",
            "retransmission": "Payload RETX trace rows, not independent loss episodes; aggregate counters sum both flows.",
            "recovery_and_loss": "Congestion-state entry counts; LOSS is not automatically labeled timeout.",
            "terminal": "Wire unique sequence bytes minus ordered application bytes at 200s; pre-processing wire observation, not exact accepted-buffer occupancy or permanent loss.",
            "guards": "Actual intervals are paired with requested windows; restore overhang=end minus requested end. Per-flow deferral/miss totals are not assigned to particular intervals.",
            "contrasts": "Treatment minus reference; percent change=100*delta/reference and null for zero or unknown reference. Jain delta is an index change.",
            "inputs": "Only compact export/config/schedule/manifest are read and hashed here. Their raw-input hashes remain in the input summaries; this script does not independently re-audit raw traces.",
            "limits": "Deterministic conditions without independent replicate/CI, no causal attribution of entire share changes, no eventual-delivery/drain-period inference, no universal K8 superiority claim.",
        }}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True, help="Original eight K3/DD and K20 compact cases, or their export root")
    parser.add_argument("--k8-root", type=Path, required=True, help="Six K8 GD/DG/GG compact cases, or their export root")
    parser.add_argument("--out", type=Path, required=True, help="New output directory; existing paths are refused")
    args = parser.parse_args()
    require(not args.out.exists(), f"Refusing to overwrite {args.out}")
    baseline = read_root(args.baseline_root, 20, MODES)
    k8 = read_root(args.k8_root, 8, MODES[1:])
    result = compare(baseline, k8)
    args.out.mkdir(parents=True, exist_ok=False)
    for name, key in (("windows.csv", "windows"), ("metrics.csv", "metrics"), ("contrasts.csv", "contrasts"),
                      ("terminal.csv", "terminal"), ("guard_intervals.csv", "guard_intervals")):
        write_csv(args.out / name, result[key])
    with (args.out / "comparison.json").open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, sort_keys=True, allow_nan=False)
        target.write("\n")
    print(f"Validated {len(result['inputs'])} cases; {len(result['windows'])} matched window rows; wrote {args.out}")


if __name__ == "__main__":
    main()
