"""Summarize matched CUBIC queue runs without publishing their large raw traces."""
import argparse
import csv
import hashlib
import json
from pathlib import Path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--runs-root", type=Path, default=Path("/tmp/cs30401-study"))
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--raw-hashes-out", type=Path, required=True)
parser.add_argument("cases", nargs="+", help="Run directory names to summarize")
args = parser.parse_args()

rows = []
raw_hashes = {}
for name in args.cases:
    run = args.runs_root / name
    manifest_path = run / "case.json"
    analysis_path = run / "study_analysis.json"
    manifest = json.loads(manifest_path.read_text())
    analysis = json.loads(analysis_path.read_text())
    if manifest["status"] != "complete" or manifest["exit_code"] != 0:
        raise ValueError(f"{name} did not complete successfully")
    if len(analysis["flows"]) != 1:
        raise ValueError(f"{name} is not a single-flow case")
    flow = next(iter(analysis["flows"].values()))
    counts = flow["counts"]
    row = {
        "case": name,
        "queue_packets": manifest["parameters"]["queue"],
        "threshold_schedule": manifest["parameters"]["parameters"],
        "duration_s": manifest["parameters"]["duration"],
        "receiver_goodput_mbps": flow["receiver_application_goodput_mbps"],
        "receiver_bytes": counts["application_delivered_bytes"],
        "retransmissions": counts["official_retransmission_rows"],
        "recovery_entries": counts["recovery_state_entries"],
        "drop_trace_rows": counts["drop_trace_rows"],
        "drop_coverage_available": analysis["drop_coverage"]["available"],
        "patch_sha256": manifest["patch_sha256"],
        "binary_sha256": manifest["binary_sha256"],
        "analysis_sha256": sha256(analysis_path),
        "manifest_sha256": sha256(manifest_path),
    }
    for event_s in (26.2, 75.0):
        matches = [event for event in analysis["path_event_windows"] if abs(event["time_s"] - event_s) < 1e-6]
        if len(matches) != 1:
            raise ValueError(f"{name} lacks exactly one {event_s}s event")
        event = matches[0]
        event_flow = next(iter(event["flows"].values()))
        key = f"event_{event_s:g}s"
        row[key + "_goodput_mbps"] = event_flow["receiver_application_goodput_mbps"]
        row[key + "_retransmissions"] = event_flow.get("official_retransmission_rows", 0)
        row[key + "_recovery_entries"] = event_flow.get("recovery_state_entries", 0)
    rows.append(row)
    raw_hashes[name] = [
        {"kind": source["kind"], "file": Path(source["path"]).name,
         "sha256": sha256(Path(source["path"]))}
        for source in analysis["inputs"]
    ]

args.out.parent.mkdir(parents=True, exist_ok=True)
with args.out.open("w", newline="") as output:
    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
print(args.out)
args.raw_hashes_out.parent.mkdir(parents=True, exist_ok=True)
args.raw_hashes_out.write_text(json.dumps(raw_hashes, indent=2) + "\n")
print(args.raw_hashes_out)
