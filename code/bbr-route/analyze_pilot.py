"""Summarize completed passive BBR diagnostics, keeping layers/metrics distinct."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

NS = 1_000_000_000
WINDOWS = {"whole": (0, 40), "common": (10, 40), "admission": (10, 15)}
MODES = {0: "STARTUP", 1: "DRAIN", 2: "ProbeBW", 3: "ProbeRTT"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inside_bin(row, lower, upper):
    start, end = int(row["bin_start_ns"]), int(row["bin_end_ns"])
    require(start < end and (end - start) == 100_000_000, "Unexpected bin width")
    intersects = start < upper and end > lower
    require(not intersects or (start >= lower and end <= upper), "Window cuts a source bin")
    return intersects


def mode_durations(rows, lower, upper):
    result = collections.Counter()
    for i, row in enumerate(rows):
        start = int(row["time_ns"])
        if start >= upper:
            continue
        end = int(rows[i + 1]["time_ns"]) if i + 1 < len(rows) else upper
        require(end >= start, "State time decreases")
        duration = max(0, min(end, upper) - max(start, lower))
        result[MODES[int(row["bbr_state"])]] += duration / NS
    return dict(result)


def analyze(run):
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    require(manifest["status"] == "success" and manifest["returncode"] == 0,
            f"Incomplete/failed run: {run}")
    require(manifest["definition"]["observe"], f"Observer not enabled: {run}")
    logs = run / "logs_ns3"
    inputs = sorted(logs.glob("bbr_*.csv"))
    require(inputs, "No observer CSVs")
    require({path.name for path in inputs} == {Path(name).name for name in manifest["outputs"]
            if Path(name).name.startswith("bbr_") and name.endswith(".csv")},
            "Observer file set differs from execution receipt")
    for path in inputs:
        entry = manifest["outputs"].get("logs_ns3/" + path.name)
        require(entry and entry["sha256"] == sha(path), f"Input differs from execution receipt: {path}")
    state_rows = read_csv(logs / "bbr_state.csv")
    rx_rows = [row for path in sorted(logs.glob("bbr_app_rx_node_*.csv")) for row in read_csv(path)]
    queue_rows = read_csv(logs / "bbr_queue_bins.csv")
    pending_rows = read_csv(logs / "bbr_queue_pending.csv")
    drop_rows = read_csv(logs / "bbr_drops.csv")
    coverage = read_csv(logs / "bbr_coverage.csv")
    require(coverage and all(int(row["connected"]) == 1 for row in coverage), "Observer hook missing")
    require(rx_rows and all(row["flow_id"] != "" for row in rx_rows), "Unidentified app connection")
    flow_ids = set(range(len(manifest["definition"]["starts"])))
    require({int(row["flow_id"]) for row in rx_rows} == flow_ids, "Receiver flow set differs from schedule")
    require({int(row["flow_id"]) for row in state_rows} == flow_ids, "BBR flow set differs from schedule")
    grouped = {flow: [row for row in state_rows if int(row["flow_id"]) == flow] for flow in flow_ids}
    for row in queue_rows:
        require(int(row["drop_after"]) == 0, "DropAfterDequeue outside served-sojourn coverage")
    queue_balance = collections.Counter()
    for row in queue_rows:
        queue_balance[(row["node_id"], row["device_id"], row["flow_id"])] += int(row["enqueued"]) - int(row["dequeued"])
    pending_balance = collections.Counter()
    for row in pending_rows:
        pending_balance[(row["node_id"], row["device_id"], row["flow_id"])] += int(row["pending_packets"])
    require({key: value for key, value in queue_balance.items() if value} ==
            {key: value for key, value in pending_balance.items() if value},
            "Queue enqueue-dequeue balance differs from censored pending counts")
    receiver_totals = collections.Counter()
    for row in rx_rows:
        receiver_totals[int(row["flow_id"])] += int(row["app_bytes"])
    for flow in flow_ids:
        connections = collections.defaultdict(list)
        for row in rx_rows:
            if int(row["flow_id"]) == flow:
                connections[(row["node_id"], row["connection_id"])].append(row)
        require(sum(int(rows[-1]["connection_total_bytes"]) for rows in connections.values()) ==
                receiver_totals[flow], "App bin totals do not reconcile with cumulative connection totals")
    node_totals = collections.Counter()
    all_connections = collections.defaultdict(list)
    for row in rx_rows:
        node_totals[row["node_id"]] += int(row["app_bytes"])
        all_connections[(row["node_id"], row["connection_id"])].append(row)
    for key, rows in all_connections.items():
        require(len({(row["flow_id"], row["local_port"], row["peer_port"]) for row in rows}) == 1,
                f"Connection changes flow/ports: {key}")
        total = 0
        previous_end = -1
        for row in rows:
            require(int(row["bin_start_ns"]) >= previous_end, "Connection bins overlap or decrease")
            previous_end = int(row["bin_end_ns"])
            total += int(row["app_bytes"])
            require(int(row["connection_total_bytes"]) == total, "Cumulative app bytes are inconsistent")
    for node, total in node_totals.items():
        require(max(int(row["sink_total_bytes"]) for row in rx_rows if row["node_id"] == node) == total,
                f"Sink total differs from all delivered app bins at node {node}")
    windows, seconds, devices = [], [], []
    for label, (start, end) in WINDOWS.items():
        lower, upper = start * NS, end * NS
        selected_rx = [row for row in rx_rows if inside_bin(row, lower, upper)]
        delivered = collections.Counter()
        for row in selected_rx:
            delivered[int(row["flow_id"])] += int(row["app_bytes"])
        rates = {str(flow): delivered[flow] * 8 / ((end - start) * 1e6) for flow in sorted(flow_ids)}
        values = list(rates.values())
        jain = sum(values) ** 2 / (len(values) * sum(value ** 2 for value in values)) if sum(values) else None
        selected_queue = [row for row in queue_rows if inside_bin(row, lower, upper)]
        visits = sum(int(row["sojourn_samples"]) for row in selected_queue)
        wait = sum(int(row["sojourn_sum_ns"]) for row in selected_queue)
        layers = dict(collections.Counter(row["layer"] for row in drop_rows
                                         if lower <= int(row["time_ns"]) < upper))
        window = {"case": manifest["case"], "window": label, "start_s": start, "end_s": end,
                  "app_goodput_mbps_by_flow": rates, "aggregate_app_goodput_mbps": sum(values),
                  "jain_equal_rate_index": jain, "drop_events_by_layer": layers,
                  "served_queue_visit_samples": visits,
                  "served_queue_visit_mean_wait_ms": wait / visits / 1e6 if visits else None,
                  "served_queue_visit_max_wait_ms": max((int(row["sojourn_max_ns"])
                                                          for row in selected_queue), default=0) / 1e6,
                  "mode_seconds_sample_hold_by_flow": {str(flow): mode_durations(rows, lower, upper)
                                                        for flow, rows in grouped.items()}}
        windows.append(window)
        by_device = collections.defaultdict(lambda: [0, 0, 0])
        for row in selected_queue:
            key = (row["node_id"], row["device_id"])
            tally = by_device[key]
            tally[0] += int(row["sojourn_samples"])
            tally[1] += int(row["sojourn_sum_ns"])
            tally[2] = max(tally[2], int(row["sojourn_max_ns"]))
        for (node, device), (count, total, maximum) in by_device.items():
            devices.append({"case": manifest["case"], "window": label, "node_id": node,
                            "device_id": device, "served_queue_visits": count,
                            "mean_visit_wait_ms": total / count / 1e6 if count else None,
                            "max_visit_wait_ms": maximum / 1e6})
    for second in range(40):
        by_flow = collections.Counter()
        for row in rx_rows:
            if second * NS <= int(row["bin_start_ns"]) < (second + 1) * NS:
                by_flow[int(row["flow_id"])] += int(row["app_bytes"])
        for flow in sorted(flow_ids):
            seconds.append({"case": manifest["case"], "start_s": second, "end_s": second + 1,
                            "flow_id": flow, "app_bytes": by_flow[flow],
                            "app_goodput_mbps": by_flow[flow] * 8 / 1e6})
    states = {}
    for flow, rows in grouped.items():
        states[str(flow)] = {"sample_count": len(rows),
                            "last_record_time_ns": int(rows[-1]["time_ns"]),
                            "max_bw_bps_min": min(int(row["max_bw_bps"]) for row in rows),
                            "max_bw_bps_max": max(int(row["max_bw_bps"]) for row in rows),
                            "rtprop_ns_min": min(int(row["rtprop_ns"]) for row in rows if row["rtprop_ns"]),
                            "rtprop_ns_max": max(int(row["rtprop_ns"]) for row in rows if row["rtprop_ns"]),
                            "last_rate_sample_acked_sacked_total_bytes": int(rows[-1]["acked_sacked_bytes_total"]),
                            "last_rate_sample_loss_total_bytes": int(rows[-1]["loss_bytes_total"])}
    record = {"case": manifest["case"], "execution_manifest_sha256": sha(manifest_path),
              "inputs": {path.name: {"bytes": path.stat().st_size, "sha256": sha(path)} for path in inputs},
              "receiver_total_app_bytes_by_flow": dict(receiver_totals), "bb_state_ranges": states,
              "queue_conservation_verified": True,
              "censored_pending_packets": sum(pending_balance.values()),
              "windows": windows, "wall_seconds": manifest["wall_seconds"],
              "raw_logs_bytes": sum(entry["bytes"] for entry in manifest["outputs"].values())}
    return record, seconds, devices


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), "Output directory must be new")
    records, seconds, devices, windows = [], [], [], []
    for run in args.runs:
        record, rows, queues = analyze(run)
        records.append(record)
        seconds.extend(rows)
        devices.extend(queues)
        for window in record["windows"]:
            flat = {key: value for key, value in window.items() if not isinstance(value, dict)}
            for flow, value in window["app_goodput_mbps_by_flow"].items():
                flat["app_goodput_mbps_flow_" + flow] = value
            flat["drop_events_by_layer_json"] = json.dumps(window["drop_events_by_layer"], sort_keys=True)
            windows.append(flat)
    # All rows use the same flow columns, including solo runs.
    all_fields = list(dict.fromkeys(key for row in windows for key in row))
    windows = [{key: row.get(key) for key in all_fields} for row in windows]
    args.out.mkdir(parents=True)
    write_csv(args.out / "pilot-windows.csv", windows)
    write_csv(args.out / "pilot-second-bins.csv", seconds)
    write_csv(args.out / "pilot-device-queues.csv", devices)
    report = {"analyzer_sha256": sha(Path(__file__)), "cases": records,
              "windows": WINDOWS, "limits": [
                  "Shared-path admission, not independent-route natural merge or a proven LEO-specific problem.",
                  "No controller or performance improvement is tested.",
                  "Queue wait is per served device-queue visit; zero waits included, packets left queued censored.",
                  "Queue drops/IPv4/TcDrop are separate event layers, not summed unique losses.",
                  "BBR ACK/loss-byte sample counters are not unique app delivery or retransmission counts.",
                  "Mode durations hold sparse ACK-driven samples, not continuous timer-state instrumentation.",
                  "Jain index describes rate equality over the declared window, not universal fairness.",
              ]}
    (args.out / "pilot-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"cases": [record["case"] for record in records], "output": str(args.out)}))


if __name__ == "__main__":
    main()
