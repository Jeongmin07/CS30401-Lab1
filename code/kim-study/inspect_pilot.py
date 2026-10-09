"""Inspect a fresh pilot; associations here do not establish loss or reordering."""
import bisect
import csv
import json
import sys
from pathlib import Path

run = Path(sys.argv[1])
truth_file = Path(sys.argv[2])
truth = list(csv.DictReader(truth_file.open(newline="")))
route_changes = []
for before, after in zip(truth, truth[1:]):
    if after["rtt_prop_ms"] and before["rtt_prop_ms"] and int(after["path_changed"]):
        route_changes.append({
            "time_s": float(after["t_s"]),
            "rtt_change_ms": round(float(after["rtt_prop_ms"]) - float(before["rtt_prop_ms"]), 3),
            "rtt_before_ms": float(before["rtt_prop_ms"]),
            "rtt_after_ms": float(after["rtt_prop_ms"]),
        })
route_times = [event["time_s"] for event in route_changes]

def trace(name):
    with (run / "logs_ns3" / name).open(newline="") as file:
        return [(int(row[1]) / 1e9, int(row[2])) for row in csv.reader(file)]

cwnd = trace("tcp_flow_0_cwnd.csv")
progress = trace("tcp_flow_0_progress.csv")
rtt = trace("tcp_flow_0_rtt.csv")
reductions = []
for (old_time, old), (time, new) in zip(cwnd, cwnd[1:]):
    if new < 0.85 * old:
        index = bisect.bisect_left(route_times, time)
        candidates = route_times[max(0, index - 1):index + 1]
        nearest = min(candidates, key=lambda candidate: abs(time - candidate)) if candidates else None
        reductions.append({"time_s": round(time, 6), "old_bytes": old,
                           "new_bytes": new, "fraction": round(new / old, 3),
                           "nearest_route_change_s": nearest,
                           "offset_from_route_change_s": round(time - nearest, 6)
                           if nearest is not None else None})

duration_ns = None
for line in (run / "config_ns3.properties").read_text().splitlines():
    if line.startswith("simulation_end_time_ns="):
        duration_ns = int(line.split("=", 1)[1])
assert duration_ns and progress, "Incomplete pilot output."
result = {
    "run": run.name,
    "simulation_duration_s": duration_ns / 1e9,
    "final_acknowledged_bytes": progress[-1][1],
    "acknowledged_rate_over_whole_run_mbps": round(progress[-1][1] * 8 / (duration_ns / 1e9) / 1e6, 6),
    "route_change_count": len(route_changes),
    "largest_path_rtt_decreases": sorted(route_changes, key=lambda e: e["rtt_change_ms"])[:5],
    "cwnd_reductions_over_15_percent": reductions,
    "trace_rows": {"cwnd": len(cwnd), "rtt": len(rtt), "progress": len(progress)},
    "limitations": ["The rate uses sender acknowledged bytes, not a separately instrumented receiver.",
                    "RTT changes include both directions; they do not prove forward-path reordering.",
                    "No packet-arrival, queue/IP/device-drop, or recovery-state traces were added.",
                    "Default PRR can adjust cwnd in small steps; the 15% single-step filter cannot establish absence of recovery.",
                    "Cwnd reductions and nearby route events are associations, not causal proof."],
}
output = run / "pilot_inspection.json"
output.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
