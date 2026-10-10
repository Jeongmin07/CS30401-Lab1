"""Compare completed compact Vegas exports using exact decimal input values."""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess

FAMILIES = ("fixed", "step", "fixed-comp", "step-comp", "leo")
WINDOWS = ("whole", "late20", "competition")
FLOW_FIELDS = (
    "flow_start_ns", "active_duration_ns", "application_bytes",
    "application_goodput_mbps", "active_interval_application_goodput_mbps",
    "official_retransmission_rows", "official_retransmission_bytes",
    "recovery_entries", "LOSS_entries", "drop_trace_rows",
    "distinct_tagged_transmissions_dropped", "TcDrop_rows_flow",
    "TcDrop_distinct_tagged_transmissions_flow",
    "wire_unique_minus_application_at_stop_bytes",
)
WINDOW_FIELDS = (
    "start_ns", "end_ns", "window_width_ns", "application_sum_bytes",
    "application_sum_goodput_mbps", "common_active_jain",
    "TcDrop_rows_all_flows_and_unmapped", "queue_sojourn_available",
)
FLOW_METRICS = {
    "application_bytes": "bytes",
    "application_goodput_mbps": "Mbps per full window",
    "active_interval_application_goodput_mbps": "Mbps per flow active interval",
    "official_retransmission_rows": "rows",
    "official_retransmission_bytes": "bytes",
    "recovery_entries": "state entries",
    "LOSS_entries": "state entries",
    "drop_trace_rows": "trace rows",
    "distinct_tagged_transmissions_dropped": "tagged transmissions",
    "TcDrop_rows_flow": "TcDrop rows",
    "TcDrop_distinct_tagged_transmissions_flow": "tagged transmissions",
}
AGGREGATE_METRICS = {
    "application_sum_bytes": "bytes",
    "application_sum_goodput_mbps": "Mbps per full window",
    "common_active_jain": "dimensionless",
    "TcDrop_rows_all_flows_and_unmapped": "TcDrop rows",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def file_record(path):
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}


def number(value):
    if value is None or value == "":
        return None
    result = Decimal(str(value))
    require(result.is_finite(), f"Non-finite number {value!r}")
    return result


def exact_equal(left, right):
    if left in (None, "") or right in (None, ""):
        return left in (None, "") and right in (None, "")
    if str(left) in ("True", "False") or str(right) in ("True", "False"):
        return str(left) == str(right)
    return number(left) == number(right)


def scalar(value):
    """JSON/CSV retain exact decimals as strings; integers stay integers."""
    if value is None:
        return None
    value = number(value)
    return int(value) if value == value.to_integral_value() else format(value, "f")


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def case_key(name):
    matches = [(family, mode) for family in FAMILIES for mode in ("base", "renew")
               if name.endswith(f"-{family}-{mode}") and name != f"{family}-{mode}"]
    require(len(matches) == 1, f"Ambiguous/undeclared case name {name!r}")
    return matches[0]


def load_export(root):
    root = root.resolve()
    export_path = root / "export.json"
    export = json.loads(export_path.read_text(encoding="utf-8"))
    inputs = [file_record(export_path)]
    tables = {}
    for filename in ("results.csv", "queue_sojourn.csv", "renewals.csv"):
        path = root / filename
        actual = file_record(path)
        declared = export["files"][filename]
        require(actual["sha256"] == declared["sha256"] and actual["bytes"] == declared["bytes"],
                f"Export receipt mismatch: {path}")
        inputs.append(actual)
        tables[filename] = read_csv(path)
    names = [entry["case"] for entry in export["cases"]]
    require(len(names) == 10 and len(set(names)) == 10, f"Expected ten distinct cases in {root}")
    cases = {}
    result_rows = {}
    queue_rows = {}
    renewals = {name: [] for name in names}
    for row in tables["results.csv"]:
        require(row["case"] in names, f"Undeclared result case {row['case']}")
        key = (row["case"], row["window"], row["flow_id"])
        require(key not in result_rows, f"Duplicate result {key}")
        for field in (*FLOW_FIELDS, *WINDOW_FIELDS):
            require(field in row, f"Missing result column {field}")
        require(number(row["end_ns"]) - number(row["start_ns"]) == number(row["window_width_ns"]),
                f"Window width mismatch: {key}")
        result_rows[key] = row
    for row in tables["queue_sojourn.csv"]:
        require(row["case"] in names, f"Undeclared queue case {row['case']}")
        key = (row["case"], row["window"], row["direction"], row["group"])
        require(key not in queue_rows, f"Duplicate queue row {key}")
        queue_rows[key] = row
    for row in tables["renewals.csv"]:
        require(row["case"] in names and row["event"] == "RENEW", "Invalid renewal case/event")
        renewals[row["case"]].append(row)
    for name in names:
        key = case_key(name)
        require(key not in cases, f"Duplicate case family/mode: {key}")
        summary_path = root / "cases" / name / "summary.json"
        manifest_path = root / "cases" / name / "case.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        inputs.extend((file_record(summary_path), file_record(manifest_path)))
        require(summary["case"] == name and manifest["case"] == name, "Case identity mismatch")
        require(manifest["status"] == "complete" and manifest["exit_code"] == 0,
                f"Incomplete/failed case {name}")
        require(summary["simulation_launch_commit"] == manifest["source_commit"],
                f"Launch commit mismatch: {name}")
        require(summary["vegas_internal_state"]["renewal_count"] == len(renewals[name]),
                f"Renewal CSV/count mismatch: {name}")
        summary_windows = {window["window"]: window for window in summary["windows"]}
        require(len(summary_windows) == len(summary["windows"]), f"Duplicate summary window {name}")
        csv_windows = {k[1] for k in result_rows if k[0] == name}
        require(csv_windows == set(summary_windows), f"CSV/summary window mismatch: {name}")
        for window_name, window in summary_windows.items():
            flows = {k[2]: row for k, row in result_rows.items() if k[:2] == (name, window_name)}
            require(set(flows) == set(window["flows"]), f"CSV/summary flow mismatch: {name}/{window_name}")
            require(sum(int(row["application_bytes"]) for row in flows.values()) == window["application_sum_bytes"],
                    f"Aggregate app bytes mismatch: {name}/{window_name}")
            for flow_id, row in flows.items():
                for field in (*FLOW_FIELDS, *WINDOW_FIELDS):
                    if field in window["flows"][flow_id]:
                        expected = window["flows"][flow_id][field]
                    elif field in window:
                        expected = window[field]
                    elif field == "window_width_ns":
                        expected = window["end_ns"] - window["start_ns"]
                    else:
                        continue
                    require(exact_equal(row[field], expected),
                            f"CSV/summary scalar mismatch: {name}/{window_name}/{flow_id}/{field}")
                require(int(row["start_ns"]) == window["start_ns"] and int(row["end_ns"]) == window["end_ns"],
                        f"CSV/summary bounds mismatch: {name}/{window_name}")
            for q in window["queue_sojourn"]:
                qkey = (name, window_name, q["direction"], q["group"])
                require(qkey in queue_rows, f"Missing queue CSV row {qkey}")
                for field in ("packet_count", "packet_bytes", "mean_ns", "minimum_ns", "p95_ns", "p99_ns", "max_ns"):
                    require(exact_equal(queue_rows[qkey][field], q[field]), f"Queue CSV/summary mismatch: {qkey}/{field}")
        renewed_max = max((int(row["base_rtt_ns"]) for row in renewals[name]), default=None)
        cases[key] = {"case": name, "summary": summary, "manifest": manifest,
                      "windows": summary_windows, "renewal_count": len(renewals[name]),
                      "max_renewed_base_rtt_ns": renewed_max,
                      "policy": summary["policy"], "simulation_launch_commit": manifest["source_commit"]}
    require(set(cases) == {(f, m) for f in FAMILIES for m in ("base", "renew")}, "Missing declared family/mode")
    return {"root": str(root), "receipt": export, "inputs": inputs, "cases": cases,
            "results": result_rows, "queue": queue_rows}


def baseline_check(v1, v2):
    checks = []
    for family in FAMILIES:
        left = v1["cases"][(family, "base")]
        right = v2["cases"][(family, "base")]
        lw, rw = set(left["windows"]), set(right["windows"])
        checks.append({"family": family, "field": "window_names", "matched": lw == rw,
                       "v1": sorted(lw), "v2": sorted(rw)})
        for window in sorted(lw | rw):
            lr = {k[2]: r for k, r in v1["results"].items() if k[:2] == (left["case"], window)}
            rr = {k[2]: r for k, r in v2["results"].items() if k[:2] == (right["case"], window)}
            checks.append({"family": family, "window": window, "field": "flow_ids",
                           "matched": set(lr) == set(rr), "v1": sorted(lr), "v2": sorted(rr)})
            for flow in sorted(set(lr) & set(rr), key=int):
                for field in (*FLOW_FIELDS, *WINDOW_FIELDS):
                    checks.append({"family": family, "window": window, "flow_id": flow, "field": field,
                                   "matched": exact_equal(lr[flow][field], rr[flow][field]),
                                   "v1": lr[flow][field], "v2": rr[flow][field]})
    return {"method": "Every exported baseline window/flow checked; numeric equality uses Decimal without tolerance. No rounding before comparison.",
            "all_matched": all(c["matched"] for c in checks), "checks": checks,
            "mismatches": [c for c in checks if not c["matched"]]}


def git_identity():
    root = Path(__file__).resolve().parents[3]
    command = ["git", "-c", f"safe.directory={root}", "-c", "core.autocrlf=true"]
    try:
        return {"git_head": subprocess.check_output(command + ["rev-parse", "HEAD"], cwd=root, text=True).strip(),
                "worktree_status": subprocess.check_output(command + ["status", "--porcelain"], cwd=root, text=True)}
    except (OSError, subprocess.CalledProcessError) as error:
        return {"git_head": None, "unavailable": str(error)}


def compare(v1, v2):
    rows = []
    case_records = []
    for family in FAMILIES:
        variants = {"baseline": (v1, v1["cases"][(family, "base")]),
                    "v1_renew": (v1, v1["cases"][(family, "renew")]),
                    "v2_renew": (v2, v2["cases"][(family, "renew")])}
        for label, (_, case) in variants.items():
            case_records.append({"family": family, "variant": label, "case": case["case"],
                                 "simulation_launch_commit": case["simulation_launch_commit"],
                                 "policy": case["policy"], "renewal_count": case["renewal_count"],
                                 "max_renewed_base_rtt_ns": case["max_renewed_base_rtt_ns"]})
        case_records.append({"family": family, "variant": "v2_baseline_validation_only",
                             "case": v2["cases"][(family, "base")]["case"],
                             "simulation_launch_commit": v2["cases"][(family, "base")]["simulation_launch_commit"],
                             "policy": v2["cases"][(family, "base")]["policy"],
                             "renewal_count": v2["cases"][(family, "base")]["renewal_count"],
                             "max_renewed_base_rtt_ns": v2["cases"][(family, "base")]["max_renewed_base_rtt_ns"]})
        for window in WINDOWS:
            available = [window in case["windows"] for _, case in variants.values()]
            require(len(set(available)) == 1, f"Unmatched requested window {family}/{window}")
            if not available[0]:
                continue
            selected = {}
            for label, (export, case) in variants.items():
                selected[label] = {k[2]: r for k, r in export["results"].items() if k[:2] == (case["case"], window)}
            flow_ids = set(selected["baseline"])
            require(all(set(value) == flow_ids for value in selected.values()), f"Unmatched flows {family}/{window}")
            first = next(iter(selected["baseline"].values()))
            start, end = int(first["start_ns"]), int(first["end_ns"])
            require(end > start, f"Empty matched window {family}/{window}")
            for flow_map in selected.values():
                require(all(int(r["start_ns"]) == start and int(r["end_ns"]) == end for r in flow_map.values()),
                        f"Unmatched interval bounds {family}/{window}")

            def append(group, metric, unit, values, active_ns=None):
                converted = {label: number(value) for label, value in values.items()}
                base, old, new = (converted[label] for label in ("baseline", "v1_renew", "v2_renew"))
                row = {"family": family, "window": window, "start_ns": start, "end_ns": end,
                       "window_width_ns": end - start, "group": group, "metric": metric, "unit": unit,
                       "active_duration_ns": active_ns,
                       "baseline": scalar(base), "v1_renew": scalar(old), "v2_renew": scalar(new),
                       "v1_minus_baseline": scalar(old - base) if base is not None and old is not None else None,
                       "v2_minus_baseline": scalar(new - base) if base is not None and new is not None else None,
                       "v2_minus_v1": scalar(new - old) if old is not None and new is not None else None}
                for label, (_, case) in variants.items():
                    row[f"{label}_case"] = case["case"]
                    row[f"{label}_renewal_count_whole_case"] = case["renewal_count"]
                    row[f"{label}_max_renewed_base_rtt_ns_whole_case"] = case["max_renewed_base_rtt_ns"]
                rows.append(row)

            for flow in sorted(flow_ids, key=int):
                active = {int(flow_map[flow]["active_duration_ns"]) for flow_map in selected.values()}
                require(len(active) == 1, f"Unmatched active durations {family}/{window}/flow{flow}")
                for metric, unit in FLOW_METRICS.items():
                    append(f"flow{flow}", metric, unit, {label: flow_map[flow][metric] for label, flow_map in selected.items()}, next(iter(active)))
            for metric, unit in AGGREGATE_METRICS.items():
                values = {label: next(iter(flow_map.values()))[metric] for label, flow_map in selected.items()}
                if metric == "common_active_jain":
                    present = [v != "" for v in values.values()]
                    require(len(set(present)) == 1, f"Unmatched Jain eligibility {family}/{window}")
                    if not present[0]:
                        continue
                    require(len(flow_ids) > 1 and all(int(r["active_duration_ns"]) == end - start for flow_map in selected.values() for r in flow_map.values()),
                            f"Jain requires the same fully active window {family}/{window}")
                for flow_map in selected.values():
                    require(all(exact_equal(r[metric], next(iter(flow_map.values()))[metric]) for r in flow_map.values()),
                            f"Inconsistent aggregate scalar {family}/{window}/{metric}")
                append("aggregate", metric, unit, values)
            queues = {label: export["queue"].get((case["case"], window, "forward", "all")) for label, (export, case) in variants.items()}
            require(len({q is None for q in queues.values()}) == 1, f"Unmatched direct queue coverage {family}/{window}")
            for metric in ("mean_ns", "p95_ns"):
                append("forward/all", f"queue_sojourn_{metric.removesuffix('_ns')}_ms", "ms; packet weighted",
                       {label: number(q[metric]) / Decimal(1000000) if q is not None else None for label, q in queues.items()})
    return rows, case_records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v1-export", type=Path, required=True)
    parser.add_argument("--v2-export", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), f"Refusing existing output directory {args.out}")
    before = git_identity()
    old = load_export(args.v1_export)
    new = load_export(args.v2_export)
    baselines = baseline_check(old, new)
    rows, cases = compare(old, new)
    report = {"schema_version": 1, "baseline_check": baselines, "cases": cases, "rows": rows,
              "method": {"intervals": "Exact matched [start,end); aggregate goodput uses all observed application bytes / full matched width.",
                         "decimals": "Exact input decimal arithmetic; values/differences are decimal strings or integers, with no display rounding.",
                         "jain": "Only nonblank source Jain values when every included flow is active for the same complete window.",
                         "queue": "Forward device FIFO, all dequeued packets, including zero wait; mean/p95 converted exactly ns to ms. Missing LEO direct queue values remain null.",
                         "renewals": "Counts and maximum RENEW base RTT refer to the whole case, not each repeated comparison window.",
                         "loss": "TcDrop is distinct from device queue drops; RECOVERY/LOSS state entries are not RTO counters.",
                         "baseline_selection": "Three-way display uses v1 baseline; v2 baseline is retained separately and exact baseline validation must pass before sharing conclusions."},
              "provenance": {"comparison_helper": file_record(Path(__file__).resolve()),
                             "comparison_git_identity_before": before,
                             "comparison_git_identity_after": git_identity(),
                             "v1": {"inputs": old["inputs"], "simulation_launch_commits": old["receipt"]["simulation_launch_commits"],
                                    "posthoc_analysis_identity": old["receipt"]["posthoc_analysis_identity"],
                                    "posthoc_export_git_head": old["receipt"]["posthoc_export_git_head"], "export_helper": old["receipt"]["export_helper"]},
                             "v2": {"inputs": new["inputs"], "simulation_launch_commits": new["receipt"]["simulation_launch_commits"],
                                    "posthoc_analysis_identity": new["receipt"]["posthoc_analysis_identity"],
                                    "posthoc_export_git_head": new["receipt"]["posthoc_export_git_head"], "export_helper": new["receipt"]["export_helper"]}}}
    args.out.mkdir(parents=True)
    with (args.out / "compare.csv").open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    report["compare_csv"] = file_record(args.out / "compare.csv")
    with (args.out / "compare.json").open("w", encoding="utf-8", newline="\n") as destination:
        json.dump(report, destination, indent=2, sort_keys=True, allow_nan=False)
        destination.write("\n")
    print(json.dumps({"out": str(args.out), "rows": len(rows), "baseline_all_matched": baselines["all_matched"],
                      "baseline_mismatches": len(baselines["mismatches"])}))
    raise SystemExit(0 if baselines["all_matched"] else 2)


if __name__ == "__main__":
    main()
