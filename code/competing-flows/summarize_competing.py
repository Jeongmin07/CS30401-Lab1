"""Validate two-flow delivery and export small evidence; Python standard library only."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

FLOW_IDS = ("0", "1")


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def jain(values):
    squared = sum(x * x for x in values)
    return None if not squared else sum(values) ** 2 / (len(values) * squared)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_case(run, out, analyzer, path_truth):
    manifest = json.loads((run / "case.json").read_text())
    if manifest["status"] != "complete" or manifest["exit_code"] != 0:
        raise ValueError(f"Incomplete case: {run}")
    analysis_path = run / "study_analysis.json"
    command = [sys.executable, str(analyzer), str(run), "--path-truth", str(path_truth),
               "--include-bins", "--output", str(analysis_path)]
    subprocess.run(command, check=True)
    analysis = json.loads(analysis_path.read_text())
    if set(analysis["flows"]) != set(FLOW_IDS):
        raise ValueError(f"Expected two traced flows, found {list(analysis['flows'])}")
    schedule = list(csv.reader((run / "schedule.csv").open(newline="")))
    if len(schedule) != 2 or [row[0] for row in schedule] != list(FLOW_IDS):
        raise ValueError("Expected exactly two schedule rows ordered 0,1")
    duration_ns = round(analysis["duration_s"] * 1e9)
    starts = [int(row[4]) for row in schedule]
    guards = [bool(row[5]) for row in schedule]
    guard_checks = {}
    windows = {"whole": (0, duration_ns), "common-active": (max(starts), duration_ns),
               "steady": (20_000_000_000, duration_ns),
               "event26": (25_700_000_000, 28_200_000_000),
               "event75": (74_500_000_000, 77_000_000_000)}
    if any(not 0 <= left < right <= duration_ns for left, right in windows.values()):
        raise ValueError("This declared analysis requires duration >=77s and starts <end")
    counters = {key: {fid: collections.Counter() for fid in FLOW_IDS} for key in windows}
    bins = collections.defaultdict(lambda: collections.Counter())
    connections, totals, flow_connections = {}, {}, collections.defaultdict(set)
    app_files = sorted((run / "logs_ns3").glob("study_app_rx*.csv"))
    if not app_files:
        raise ValueError("Missing receiver application trace")
    for path in app_files:
        previous = -1
        with path.open(newline="") as source:
            for row in csv.DictReader(source):
                time = int(row["time_ns"])
                fid, size = row["flow_id"], int(row["payload_bytes"])
                if time < previous or not 0 <= time < duration_ns or fid not in FLOW_IDS:
                    raise ValueError(f"Invalid application row in {path}: {row}")
                previous = time
                key = (row["node_id"], row["local_port"], row["connection_id"])
                peer = (row["peer_ip"], row["peer_port"], fid)
                if key in connections and connections[key] != peer:
                    raise ValueError("Connection identity changed between flows")
                connections[key] = peer
                flow_connections[fid].add(key)
                totals[key] = totals.get(key, 0) + size
                if totals[key] != int(row["connection_total_rx_bytes"]):
                    raise ValueError("Per-connection delivered-byte total mismatch")
                bins[time // 1_000_000_000][fid] += size
                for name, (left, right) in windows.items():
                    if left <= time < right:
                        counters[name][fid]["application_bytes"] += size
    if len(connections) != 2 or any(len(flow_connections[fid]) != 1 for fid in FLOW_IDS):
        raise ValueError(f"Expected one receiver connection per flow: {connections}")
    if len({(peer[0], peer[1]) for peer in connections.values()}) != 2:
        raise ValueError("Sender peer socket identities are not distinct")
    for fid in FLOW_IDS:
        flow = analysis["flows"][fid]
        delivered = counters["whole"][fid]["application_bytes"]
        if not delivered or delivered != flow["counts"].get("application_delivered_bytes", 0):
            raise ValueError("Receiver delivery differs from existing analyzer")
        bins_sum = sum(row["bytes"] for row in flow["receiver_application_bins"])
        if bins_sum != delivered:
            raise ValueError("Existing analyzer bin totals differ from receiver delivery")
        event_path = run / "logs_ns3" / f"tcp_flow_{fid}_study_events.csv"
        threshold_sets = []
        with event_path.open(newline="") as source:
            for row in csv.DictReader(source):
                if row["flow_id"] != fid:
                    raise ValueError("Event trace belongs to another flow")
                time = int(row["time_ns"])
                if row["event"] == "THRESHOLD_SET":
                    threshold_sets.append(row)
                field = None
                if row["event"] == "CONG" and row["old_value"] != row["new_value"]:
                    field = {"3": "recovery_entries", "4": "loss_entries"}.get(row["new_value"])
                if field:
                    for name, (left, right) in windows.items():
                        if left <= time < right:
                            counters[name][fid][field] += 1
        if flow["initial_retransmission_threshold"] != 3:
            raise ValueError(f"Expected initial K3 for flow {fid}")
        controls = dict(token.split("=", 1) for token in schedule[int(fid)][5].split(";") if "=" in token)
        expected_sets = []
        if guards[int(fid)]:
            threshold = int(controls["study_threshold"])
            requested = [tuple(map(int, part.split(":"))) for part in controls["study_windows"].split("|")]
            if any(left <= starts[int(fid)] or right > duration_ns for left, right in requested):
                raise ValueError("This validator expects guards after both starts and before simulation end")
            expected_sets = [(left, threshold) for left, _ in requested]
        actual_sets = [(int(row["time_ns"]), int(row["new_value"])) for row in threshold_sets]
        if actual_sets != expected_sets or any(int(row["threshold"]) != int(row["new_value"]) for row in threshold_sets):
            raise ValueError(f"Guard activation time/K does not match schedule for flow {fid}")
        guard_checks[fid] = {"initial_k": 3, "expected_sets": expected_sets,
                             "observed_sets": actual_sets, "matched": True}
        with (run / "logs_ns3" / f"tcp_flow_{fid}_study_packets.csv").open(newline="") as source:
            for row in csv.DictReader(source):
                if row["flow_id"] != fid:
                    raise ValueError("Packet trace belongs to another flow")
                if row["event"] == "RETX" and int(row["payload_bytes"]) > 0:
                    time = int(row["time_ns"])
                    for name, (left, right) in windows.items():
                        if left <= time < right:
                            counters[name][fid]["retransmission_rows"] += 1
        for own, existing in (("recovery_entries", "recovery_state_entries"),
                              ("loss_entries", "loss_state_entries"),
                              ("retransmission_rows", "official_retransmission_rows")):
            if counters["whole"][fid][own] != flow["counts"].get(existing, 0):
                raise ValueError(f"Whole-run {own} differs from existing analyzer")
    rows = []
    for name, (left, right) in windows.items():
        values = [counters[name][fid]["application_bytes"] for fid in FLOW_IDS]
        rates = [value * 8 / ((right-left) / 1e9) / 1e6 for value in values]
        row = {"case": run.name, "window": name, "start_s": left/1e9, "end_s": right/1e9,
               "guard0": guards[0], "guard1": guards[1], "start0_s": starts[0]/1e9,
               "start1_s": starts[1]/1e9, "total_goodput_mbps": sum(rates),
               "jain_index": jain(values)}
        for fid, value, rate in zip(FLOW_IDS, values, rates):
            row.update({f"flow{fid}_bytes": value, f"flow{fid}_goodput_mbps": rate,
                        f"flow{fid}_share": value/sum(values) if sum(values) else None})
            for field in ("retransmission_rows", "recovery_entries", "loss_entries"):
                row[f"flow{fid}_{field}"] = counters[name][fid][field]
        rows.append(row)
    bin_rows = []
    for index in range((duration_ns + 999_999_999) // 1_000_000_000):
        left, right = index * 1_000_000_000, min(duration_ns, (index+1)*1_000_000_000)
        values = [bins[index][fid] for fid in FLOW_IDS]
        bin_rows.append({"case": run.name, "start_s": left/1e9, "end_s": right/1e9,
                         "both_scheduled_active": left >= max(starts),
                         "flow0_bytes": values[0], "flow1_bytes": values[1],
                         "total_goodput_mbps": sum(values)*8/((right-left)/1e9)/1e6,
                         "jain_index": jain(values) if left >= max(starts) else None})
    inputs = [{"path": str(path.relative_to(run)), "sha256": digest(path), "bytes": path.stat().st_size}
              for path in sorted((run / "logs_ns3").glob("*.csv"))]
    compact = {"case": run.name, "source_commit": manifest["source_commit"],
               "analysis_command": command, "analysis_sha256": digest(analysis_path),
               "analyzer_sha256": digest(analyzer), "exporter_sha256": digest(__file__),
               "path_truth_sha256": digest(path_truth), "connection_validation": [
                   {"node": k[0], "local_port": k[1], "connection_id": k[2],
                    "peer_ip": v[0], "peer_port": v[1], "flow_id": v[2],
                    "delivered_bytes": totals[k]} for k, v in sorted(connections.items())],
               "guard_validation": guard_checks,
               "drop_coverage": analysis["drop_coverage"],
               "drop_rows_without_usable_transmission_tag": analysis["drop_rows_without_usable_transmission_tag"],
               "raw_inputs": inputs, "windows": rows, "flows": {}}
    for fid in FLOW_IDS:
        compact["flows"][fid] = {key: analysis["flows"][fid].get(key) for key in (
            "counts", "distinct_tagged_transmissions_dropped", "smoothed_rtt",
            "protection_intervals", "unfinished_protection_start_ns", "restore_deferrals",
            "restore_deadlines_missed", "initial_retransmission_threshold")}
    destination = out / "cases" / run.name
    destination.mkdir(parents=True)
    for name in ("case.json", "config_ns3.properties", "schedule.csv"):
        shutil.copyfile(run / name, destination / name)
    write_json(destination / "summary.json", compact)
    print(f"Validated/exported {run.name}: total {rows[0]['total_goodput_mbps']:.6f} Mbit/s", flush=True)
    return rows, bin_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/cs30401-competing"))
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--analyzer", type=Path, required=True)
    parser.add_argument("--path-truth", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError(f"Refusing to overwrite export directory {args.out}")
    args.out.mkdir(parents=True)
    rows, bins = [], []
    for name in args.cases:
        if Path(name).name != name:
            raise ValueError("Case name must not contain a path")
        result, result_bins = export_case(args.root / name, args.out, args.analyzer, args.path_truth)
        rows.extend(result)
        bins.extend(result_bins)
    for name, data in (("results.csv", rows), ("one_second_bins.csv", bins)):
        with (args.out / name).open("w", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    write_json(args.out / "method.json", {
        "windows": "Half-open [start,end) nanosecond intervals; same denominator for both flows",
        "goodput": "Unique ordered application payload bytes, not sink-wide totals or sender ACK progress",
        "fairness": "Jain index on two flows over the same window; null for no delivery",
        "common_active": "Begins at max(declared start times), not first app delivery",
        "bins": "1s from app timestamps; fairness omitted before both scheduled starts",
        "rtt": "Whole-run time-weighted sender smoothed RTT; not raw RTT/queueing-only delay",
        "retransmission": "RETX trace rows with data payload>0, not independent loss episodes",
        "loss": "LOSS state entries; not automatically interpreted as timeout",
        "inputs": "All raw/legacy CSV hashes retained; raw traces and full analysis stay outside Git",
        "sampling": "Deterministic cases, no independent seed samples/confidence intervals"})


if __name__ == "__main__":
    main()
