"""Export compact, source-backed evidence from a completed post-hoc matrix.

python export_evidence.py --analysis-root MATRIX_DIR --out NEW_EXPORT_DIR
Never copies raw CSV or full original study analysis. Never edits a run.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

NS = 1_000_000_000


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def artifact(path):
    path = Path(path)
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
            f"Artifact changed while hashing: {path}")
    return {"path": str(path), "bytes": after.st_size, "sha256": h.hexdigest()}


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def write_csv(path, columns, records):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def flow_starts(run, summary):
    driver = summary.get("driver_validation", {})
    if driver.get("available"):
        return {str(int(row["flow_id"])): int(row["start_ns"])
                for row in driver["driver_flow_life_summary"]}
    schedule = run / "schedule.csv"
    require(schedule.exists(), "Actual flow-start metadata is required")
    with schedule.open(newline="") as stream:
        return {str(int(row[0])): int(row[4]) for row in csv.reader(stream) if row}


def losses(run, summary):
    """Independent layer-specific recount: queue drops do not cover TcDrop."""
    path = run / "logs_ns3/study_drops.csv"
    expected = next((item["sha256"] for item in summary["input_artifacts"] if Path(item["path"]) == path), None)
    require(expected and artifact(path)["sha256"] == expected, "Original drop CSV changed since analysis")
    perflow, global_layers, tagged = defaultdict(Counter), defaultdict(Counter), defaultdict(set)
    examples, count = {}, 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        previous = -1
        for row in csv.DictReader(stream):
            time = int(row["time_ns"])
            require(time >= previous, "Nonchronological drop trace")
            previous, count = time, count + 1
            fid, tx, layer = row.get("flow_id", ""), row.get("tx_id", ""), row["layer"]
            fid = str(int(fid)) if fid else "unmapped"
            sample_key = (layer, fid)
            examples.setdefault(sample_key, row)
            for window in summary["windows"]:
                if window["start_ns"] <= time < window["end_ns"]:
                    name = window["window"]
                    perflow[(name, fid)][layer] += 1
                    global_layers[name][layer] += 1
                    if fid != "unmapped" and tx and int(tx) > 0:
                        tagged[(name, fid, layer)].add(int(tx))
    for window in summary["windows"]:
        require(dict(global_layers[window["window"]]) == dict(window["drop_rows_by_layer"]),
                "Independent drop-layer recount disagrees with analyzer")
    return perflow, global_layers, tagged, {
        "artifact": artifact(path), "drop_trace_rows": count,
        "first_example_per_layer_and_flow": [{"layer": key[0], "flow_id": key[1], "row": row}
                                            for key, row in sorted(examples.items())],
        "qualification": "Layer rows may duplicate one physical loss. Distinct tx_id is counted within flow and layer. Queue DropBeforeEnqueue=0 does not imply network loss=0: TrafficControl TcDrop can occur before a full device queue accepts the packet. Device4294967295 is the TcDrop hook's unknown-device sentinel, not a physical device index."}


def export_case(case, output):
    require(case["status"] == "complete", "Refusing incomplete analysis case")
    name, run = case["case"], Path(case["run"])
    base = Path(case["out"])
    summary_path, study_path = base / "vegas/summary.json", base / "study-analysis.json"
    for record in case["output_artifacts"]:
        require(artifact(record["path"])["sha256"] == record["sha256"], "Analysis output changed since wrapper finished")
    summary, study, manifest = read(summary_path), read(study_path), read(run / "case.json")
    require(manifest["status"] == "complete" and manifest["exit_code"] == 0
            and manifest["source_commit"] == case["simulation_launch_commit"],
            "Original simulation manifest no longer matches analysis provenance")
    require(artifact(run / "case.json")["sha256"] == case["original_manifest"]["sha256"],
            "Original case manifest changed")
    starts = flow_starts(run, summary)
    perflow_drops, all_drops, tagged, drop_audit = losses(run, summary)
    prefix = name.rsplit("-", 1)[0]
    mode = name.rsplit("-", 1)[1]
    result_rows, queue_rows, renewal_rows, windows = [], [], [], []
    whole_flows = summary["windows"][0]["flows"]
    whole_rtt = {fid: flow.get("smoothed_rtt") for fid, flow in study["flows"].items()}
    for window in summary["windows"]:
        label, width = window["window"], window["end_ns"] - window["start_ns"]
        eligible, rates = True, []
        for fid, metrics in window["flows"].items():
            require(fid in starts, "No actual start time for observed flow")
            active = max(0, window["end_ns"] - max(window["start_ns"], starts[fid]))
            if "active_duration_ns" in metrics:
                require(metrics["active_duration_ns"] == active, "Active-window denominator differs from driver start")
            eligible = eligible and active == width
            rate = metrics["application_bytes"] * 8 * NS / width / 1e6
            require(math.isclose(rate, metrics["application_goodput_mbps"], rel_tol=1e-12, abs_tol=1e-12),
                    "App window rate does not match exact window denominator")
            rates.append(rate)
        jain = (sum(rates) ** 2 / (len(rates) * sum(value * value for value in rates))
                if len(rates) > 1 and eligible and sum(value * value for value in rates) else None)
        compact = {key: value for key, value in window.items() if key not in ("queue_sojourn", "queue_occupancy")}
        compact["common_active_jain"] = jain
        compact["layer_rows_by_flow"] = {fid: dict(perflow_drops[(label, fid)])
                                         for fid in window["flows"]}
        compact["unmapped_drop_layer_rows"] = dict(perflow_drops[(label, "unmapped")])
        compact["queue_sojourn"] = window.get("queue_sojourn", [])
        compact["queue_occupancy"] = window.get("queue_occupancy", [])
        windows.append(compact)
        for fid, metrics in window["flows"].items():
            active = max(0, window["end_ns"] - max(window["start_ns"], starts[fid]))
            row = {"case": name, "condition": prefix, "mode": mode, "window": label,
                   "start_ns": window["start_ns"], "end_ns": window["end_ns"],
                   "window_width_ns": width, "flow_id": fid, "flow_start_ns": starts[fid],
                   "active_duration_ns": active, "application_bytes": metrics["application_bytes"],
                   "application_goodput_mbps": metrics["application_goodput_mbps"],
                   "active_interval_application_goodput_mbps": metrics["application_bytes"] * 8 * NS / active / 1e6 if active else None,
                   "application_sum_bytes": window["application_sum_bytes"],
                   "application_sum_goodput_mbps": window["application_sum_goodput_mbps"],
                   "common_active_jain": jain, "official_retransmission_rows": metrics["official_retransmission_rows"],
                   "official_retransmission_bytes": metrics["official_retransmission_bytes"],
                   "recovery_entries": metrics["recovery_entries"], "LOSS_entries": metrics["LOSS_entries"],
                   "drop_trace_rows": metrics["drop_trace_rows"],
                   "distinct_tagged_transmissions_dropped": metrics["distinct_tagged_transmissions_dropped"],
                   "TcDrop_rows_flow": perflow_drops[(label, fid)]["TcDrop"],
                   "TcDrop_distinct_tagged_transmissions_flow": len(tagged[(label, fid, "TcDrop")]),
                   "TcDrop_rows_all_flows_and_unmapped": all_drops[label]["TcDrop"],
                   "queue_sojourn_available": summary["queue_instrumentation"]["available"],
                   "wire_unique_minus_application_at_stop_bytes": summary["application_and_terminal_validation"]["wire_application_terminal"][fid]["wire_unique_minus_application_bytes"] if label == "whole" else None}
            result_rows.append(row)
        for group in window.get("queue_sojourn", []):
            queue_rows.append({"case": name, "window": label, "start_ns": window["start_ns"],
                               "end_ns": window["end_ns"], **group})
    vegas = summary["vegas_internal_state"]
    for event in vegas.get("renewal_events", []):
        renewal_rows.append({"case": name, "mode": mode, **event})
    raw = []
    for path in sorted(run.rglob("*")):
        require(not path.is_symlink(), f"Original run symlink needs explicit treatment: {path}")
        if path.is_file():
            entry = artifact(path)
            entry["relative_path"] = str(path.relative_to(run))
            raw.append(entry)
    compact_queue = {key: value for key, value in summary["queue_instrumentation"].items()
                     if key != "pending_packets_at_stop"}
    compact_queue["pending_packet_records_count"] = len(summary["queue_instrumentation"].get("pending_packets_at_stop", []))
    compact_vegas = {key: value for key, value in vegas.items() if key != "renewal_events"}
    compact_vegas["renewal_events_export"] = "../../renewals.csv (filter case)"
    current_mismatch = [item for item in summary["validation"]["currently_present_declared_artifacts"]
                        if not item["matches_launch_declaration"]]
    compact = {"schema_version": 1, "case": name, "duration_ns": summary["duration_ns"],
               "simulation_launch_commit": manifest["source_commit"], "policy": manifest["policy"],
               "original_manifest": "case.json", "windows": windows,
               "application_and_terminal_validation": summary["application_and_terminal_validation"],
               "drop_coverage": summary["drop_coverage"], "independent_layer_drop_audit": drop_audit,
               "queue_instrumentation": compact_queue, "vegas_internal_state": compact_vegas,
               "whole_run_smoothed_rtt": whole_rtt, "driver_validation": summary["driver_validation"],
               "original_study_analysis_check": summary["original_study_analysis_check"],
               "current_artifact_mismatches_from_launch": current_mismatch,
               "analysis_sources": summary["analysis_sources"], "consumed_analysis_inputs": summary["input_artifacts"],
               "full_analysis_artifacts": [artifact(summary_path), artifact(study_path)],
               "all_original_regular_files": raw, "method": summary["method"]}
    target = output / "cases" / name
    target.mkdir(parents=True)
    shutil.copyfile(run / "case.json", target / "case.json")
    for filename in ("config_driver.json", "config_ns3.properties", "schedule.csv"):
        if (run / filename).exists():
            require((run / filename).stat().st_size <= 64 * 1024, "Config/schedule too large for compact export")
            shutil.copyfile(run / filename, target / filename)
    write_json(target / "summary.json", compact)
    write_json(target / "analysis-execution.json", case)
    return result_rows, queue_rows, renewal_rows, {"case": name, "simulation_launch_commit": manifest["source_commit"],
        "whole_application_bytes_by_flow": {fid: item["application_bytes"] for fid, item in whole_flows.items()},
        "original_regular_files": len(raw), "original_bytes": sum(item["bytes"] for item in raw),
        "renewals": vegas.get("renewal_count"), "windows": len(windows),
        "whole_network_drop_layer_rows": summary["windows"][0]["drop_rows_by_layer"],
        "whole_queue_drop_rows": {key: value for key, value in compact_queue.get("event_rows_by_kind", {}).items() if "Drop" in key}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), f"Refusing existing export: {args.out}")
    matrix_path = args.analysis_root / "matrix.json"
    matrix = read(matrix_path)
    require(matrix["status"] == "complete" and matrix["cases"], "Completed analysis matrix is required")
    require(len({case["case"] for case in matrix["cases"]}) == len(matrix["cases"]), "Duplicate cases")
    args.out.mkdir(parents=True)
    result_rows, queue_rows, renewal_rows, cases = [], [], [], []
    for case in matrix["cases"]:
        results, queues, renewals, info = export_case(case, args.out)
        result_rows.extend(results)
        queue_rows.extend(queues)
        renewal_rows.extend(renewals)
        cases.append(info)
        print(json.dumps({"case": info["case"], "export": "passed", "renewals": info["renewals"]}), flush=True)
    results_columns = ["case", "condition", "mode", "window", "start_ns", "end_ns", "window_width_ns", "flow_id",
        "flow_start_ns", "active_duration_ns", "application_bytes", "application_goodput_mbps",
        "active_interval_application_goodput_mbps", "application_sum_bytes", "application_sum_goodput_mbps",
        "common_active_jain", "official_retransmission_rows", "official_retransmission_bytes", "recovery_entries",
        "LOSS_entries", "drop_trace_rows", "distinct_tagged_transmissions_dropped", "TcDrop_rows_flow",
        "TcDrop_distinct_tagged_transmissions_flow", "TcDrop_rows_all_flows_and_unmapped", "queue_sojourn_available",
        "wire_unique_minus_application_at_stop_bytes"]
    queue_columns = ["case", "window", "start_ns", "end_ns", "direction", "group", "packet_count", "packet_bytes",
                     "mean_ns", "minimum_ns", "p95_ns", "p99_ns", "max_ns"]
    renewal_columns = ["case", "mode", "time_ns", "vegas_instance", "event", "base_rtt_ns", "cycle_min_rtt_ns",
        "rtt_samples", "cwnd_before_bytes", "cwnd_after_bytes", "ssthresh_bytes", "diff_pkts", "cong_state",
        "renewal_enabled", "renewal_rounds", "renewal_count", "old_base_rtt_ns", "recent_min_ns", "history_rounds",
        "history_elapsed_ns", "valid_renewal_cycle", "ssthresh_before_bytes", "announced_state"]
    write_csv(args.out / "results.csv", results_columns, result_rows)
    write_csv(args.out / "queue_sojourn.csv", queue_columns, queue_rows)
    write_csv(args.out / "renewals.csv", renewal_columns, renewal_rows)
    repo = Path(__file__).resolve().parents[2]
    process = subprocess.run(["git", "-c", f"safe.directory={repo}", "-c", "core.autocrlf=true", "rev-parse", "HEAD"],
                             cwd=repo, capture_output=True, text=True)
    identity = {"export_helper": artifact(__file__), "posthoc_export_git_head": process.stdout.strip() if process.returncode == 0 else None,
                "simulation_launch_commits": sorted({item["simulation_launch_commit"] for item in cases}),
                "analysis_matrix": artifact(matrix_path), "analysis_sources": matrix["sources"],
                "posthoc_analysis_identity": matrix["posthoc_helper_identity"], "cases": cases,
                "files": {path.name: artifact(path) for path in sorted(args.out.glob("*.csv"))},
                "qualifications": [
                    "Export and analysis helpers were added after simulation; their Git identities/hashes are separate from original launch commit82ad34a975d4b15f8a536527f8ea4f0cf6e41624 (or the explicit replay launch commit).",
                    "App rate=delivered bytes/full matched-window duration; active-interval rate is separately named and excludes the competitor's pre-start time. Whole flow1 has120 active seconds inside200 observation seconds; these denominators must not be compared interchangeably.",
                    "Jain is emitted only when two or more flows are active throughout the identical common window. Whole-window Jain is blank when competitor starts at80 seconds.",
                    "Queue packet-weighted waiting excludes serialization/propagation; queue occupancy is time weighted. Absent LEO queue observations remain unavailable. Smoothed RTT is separately labeled and is not queue delay.",
                    "Queue-drop zero is not network-drop zero. Raw per-layer TcDrop counts and distinct tagged transmissions are independently recounted. LOSS state is not automatically an RTO; repeated layer rows are not independent physical losses.",
                    "Wire payload union minus receiver app delivery is a terminal observation, not proof of eventual delivery or accepted TCP bytes. No new implementation/causality/fairness claim is inferred solely from higher foreground throughput.",
                    "Every original regular run file is SHA256/byte inventoried. Raw logs, full original analyses and console outputs remain outside this Git-oriented export. Per-case summary contains bounded derived evidence; original manifests/small config are copied unchanged."]}
    write_json(args.out / "export.json", identity)
    print(json.dumps({"out": str(args.out), "cases": len(cases), "results_rows": len(result_rows),
                      "queue_rows": len(queue_rows), "renewal_rows": len(renewal_rows), "status": "complete"}))


if __name__ == "__main__":
    main()
