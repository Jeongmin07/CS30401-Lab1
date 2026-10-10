"""Export compact evidence from three completed Vegas pilots; stdlib only.

No simulations, analyzer invocation, original-file edits or raw-log copies.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shutil


CASES = ("topic-vegas-q100-100m-dynamic", "topic-vegas-fixed90ms", "topic-vegas-step90to97ms")
IMAGE_DIGEST = "sha256:3cb4877c73b4ae5e3542c1567b6761a8913056dd429d8a18f7c40aeeb399b3b4"
MICRO_WINDOWS = (("whole", 0, 20_000_000_000), ("pre-step", 0, 5_000_000_000),
                 ("post-step", 5_000_000_000, 20_000_000_000), ("late", 15_000_000_000, 20_000_000_000))
LEO_WINDOWS = (("whole", 0, 200_000_000_000), ("pre121", 111_600_000_000, 121_600_000_000),
               ("post121", 131_600_000_000, 141_600_000_000), ("middle", 150_000_000_000, 160_000_000_000),
               ("pre187", 177_400_000_000, 187_400_000_000), ("post187", 190_000_000_000, 200_000_000_000))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    before = path.stat()
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns), f"Input changed while hashing: {path}")
    return value.hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(value, target, indent=2, sort_keys=True, allow_nan=False)
        target.write("\n")


def source_record(path):
    require(path.is_file(), f"Missing inspected source: {path}")
    return {"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size}


def delay_contract(run, manifest):
    if manifest["parameters"]["kind"] != "micro":
        return None
    source = Path("/home/ubuntu/ns-3.48/scratch/study_micro/study_micro.cc")
    time_source = Path("/home/ubuntu/ns-3.48/src/core/model/nstime.h")
    text, time_text = source.read_text(), time_source.read_text()
    require("MilliSeconds(before_ms)" in text and "MilliSeconds(after_ms)" in text
            and "MilliSeconds(uint64_t value)" in time_text, "Synthetic delay conversion contract changed")
    parameters = manifest["parameters"]
    before, after = parameters["before_ms"], parameters["after_ms"]
    require(before >= 0 and after >= 0, "Negative synthetic delay is unsupported")
    actual_before, actual_after = int(before), int(after)
    latencies = []
    for path in sorted((run / "logs_ns3").glob("study_rx*.csv")):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if int(row["payload_bytes"]) and int(row["time_ns"]) >= 18_000_000_000:
                    require(row["tagged"] == "1", "Late synthetic payload is untagged")
                    latency = int(row["time_ns"]) - int(row["tx_time_ns"])
                    require(latency >= 0, "Negative tagged forward latency")
                    latencies.append(latency)
    require(latencies, "No late tagged synthetic payload")
    minimum = min(latencies)
    require(actual_after * 1e6 <= minimum < (actual_after + 1) * 1e6,
            "Late forward latency does not support effective integer-ms delay")
    mismatch = before != actual_before or after != actual_after
    if mismatch:
        require(minimum < after * 1e6, "No independent wire evidence supporting nominal/effective mismatch")
    return {"event_s": parameters["event_s"], "requested_one_way_before_ms": before,
            "requested_one_way_after_ms": after, "effective_one_way_before_ms": actual_before,
            "effective_one_way_after_ms": actual_after, "nominal_propagation_rtt_before_ms": 2 * before,
            "nominal_propagation_rtt_after_ms": 2 * after, "effective_propagation_rtt_before_ms": 2 * actual_before,
            "effective_propagation_rtt_after_ms": 2 * actual_after,
            "effective_propagation_rtt_change_ms": 2 * (actual_after - actual_before),
            "nominal_effective_mismatch": mismatch, "late_payload_observations": len(latencies),
            "late_forward_latency_min_ns": minimum, "late_forward_latency_max_ns": max(latencies),
            "qualification": "MilliSeconds(uint64_t) truncates nonnegative double millisecond arguments; original run ID/manifest retained. Forward latency includes serialization/queueing, not RTT.",
            "inspected_source": [source_record(source) | {"locators": [73, 93, 94]},
                                 source_record(time_source) | {"locators": [1290, 1292]}]}


def export_case(run, destination):
    manifest = json.loads((run / "case.json").read_text())
    analysis = json.loads((run / "analysis.json").read_text())
    require(manifest["case"] == run.name and manifest["status"] == "complete" and manifest["exit_code"] == 0,
            f"Incomplete/mislabelled run: {run}")
    parameters = manifest["parameters"]
    require(parameters["cc"] == "TcpVegas" and parameters["parameters"] == "", "Expected Vegas with no guard controls")
    require(manifest["official_image_digest"] == IMAGE_DIGEST, "Unexpected declared official image digest")
    require(set(analysis["flows"]) == {"0"}, "Expected exactly one analyzed flow")
    flow = analysis["flows"]["0"]
    require(flow["initial_retransmission_threshold"] == 3 and flow["protection_intervals"] == []
            and flow["unfinished_protection_start_ns"] is None and flow["restore_deferrals"] == 0
            and flow["restore_deadlines_missed"] == 0, "Analyzer reports an enabled guard")
    micro = parameters["kind"] == "micro"
    windows = MICRO_WINDOWS if micro else LEO_WINDOWS
    cutoff = windows[0][2]
    require(analysis["duration_s"] * 1e9 == cutoff and parameters["duration"] * 1e9 == cutoff,
            "Declared/analysis duration differs from intended window coverage")
    paths = sorted((run / "logs_ns3").glob("study_app_rx*.csv"))
    require(paths, "Missing receiver application log")
    totals = {name: 0 for name, _, _ in windows}
    connections, app_count, app_first, app_last = {}, 0, None, None
    for path in paths:
        previous = -1
        with path.open(newline="", encoding="utf-8-sig") as source:
            for line, row in enumerate(csv.DictReader(source), 2):
                time, size = int(row["time_ns"]), int(row["payload_bytes"])
                require(previous <= time < cutoff and time >= 0 and size > 0 and row["flow_id"] == "0",
                        f"Invalid application row: {path}:{line}")
                previous = time
                key = (row["node_id"], row["local_port"], row["connection_id"], row["peer_ip"], row["peer_port"])
                connections[key] = connections.get(key, 0) + size
                require(connections[key] == int(row["connection_total_rx_bytes"]), "Connection delivered-byte totals disagree")
                require(connections[key] == int(row["sink_total_rx_bytes"]), "Expected single-flow sink totals")
                app_count += 1
                app_first = time if app_first is None else min(app_first, time)
                app_last = time if app_last is None else max(app_last, time)
                for name, left, right in windows:
                    if left <= time < right:
                        totals[name] += size
    require(len(connections) == 1, "Expected one receiver connection")
    require(totals["whole"] == flow["counts"]["application_delivered_bytes"], "Independent app total differs from analyzer")
    goodput = totals["whole"] * 8 / (cutoff / 1e9) / 1e6
    require(math.isclose(goodput, flow["receiver_application_goodput_mbps"], rel_tol=1e-12), "Analyzer app goodput disagrees")
    require(sum(row["bytes"] for row in flow["receiver_application_bins"]) == totals["whole"], "Analyzer bin totals disagree")
    for filename in ("config_ns3.properties", "schedule.csv"):
        if f"{filename}_sha256" in manifest:
            require(digest(run / filename) == manifest[f"{filename}_sha256"], f"Original manifest hash disagrees: {filename}")
    contract = delay_contract(run, manifest)
    output_rows = [{"case": run.name, "kind": parameters["kind"], "cc": parameters["cc"],
                   "rate_mbps": parameters["rate"], "queue_pkts": parameters["queue"], "window": name,
                   "start_ns": left, "end_ns": right, "start_s": left / 1e9, "end_s": right / 1e9,
                   "application_bytes": totals[name], "application_goodput_mbps": totals[name] * 8 / ((right-left) / 1e9) / 1e6}
                  for name, left, right in windows]
    original_files = []
    for path in sorted(run.rglob("*")):
        require(not path.is_symlink(), f"Symlink in original run is unsupported: {path}")
        if path.is_file():
            original_files.append({"path": path.relative_to(run).as_posix(), "sha256": digest(path), "bytes": path.stat().st_size})
    compact = {"case": run.name, "run_dir": str(run), "windows": output_rows,
               "application_validation": {"matched_analyzer_total_goodput_and_bins": True, "payload_rows": app_count,
                   "connection_count": len(connections), "first_delivery_ns": app_first, "last_delivery_ns": app_last},
               "counts_from_existing_analysis": flow["counts"], "smoothed_rtt_from_existing_analysis": flow["smoothed_rtt"],
               "guard_validation": {"parameters_empty": True, "initial_threshold": 3, "protection_intervals": []},
               "synthetic_delay_contract": contract, "all_original_regular_files": original_files}
    destination.mkdir(parents=True)
    shutil.copyfile(run / "case.json", destination / "case.json")
    if not micro:
        for filename in ("config_ns3.properties", "schedule.csv"):
            require((run / filename).stat().st_size <= 65536, "LEO configuration unexpectedly large")
            shutil.copyfile(run / filename, destination / filename)
    write_json(destination / "summary.json", compact)
    return output_rows, compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/cs30401-study"))
    parser.add_argument("--out", type=Path, default=Path("/tmp/cs30401-topic-screening-export"))
    parser.add_argument("--launch-commit", required=True, help="Full launch git HEAD supplied by operator; absent from original runner manifest")
    parser.add_argument("--runner", type=Path, default=Path("/work/code/kim-study/run_study.py"))
    parser.add_argument("--analyzer", type=Path, default=Path("/work/code/kim-study/analyze_study.py"))
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.launch_commit), "Supply a full 40-character lowercase launch commit")
    require(not args.out.exists(), f"Refusing to overwrite export: {args.out}")
    args.out.mkdir(parents=True, exist_ok=False)
    results, cases = [], []
    for name in CASES:
        rows, summary = export_case(args.root / name, args.out / "cases" / name)
        results.extend(rows)
        cases.append({"case": name, "original_regular_files": len(summary["all_original_regular_files"]),
                      "original_bytes": sum(row["bytes"] for row in summary["all_original_regular_files"]),
                      "whole_application_bytes": rows[0]["application_bytes"]})
    with (args.out / "results.csv").open("x", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(results[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    write_json(args.out / "method.json", {"schema_version": 1, "cases": cases,
        "launch_source_commit": args.launch_commit,
        "launch_source_commit_qualification": "Operator-supplied launch git HEAD. The original run_study.py runner did NOT record source commit; this field is a later provenance annotation, not an original manifest field.",
        "official_image_digest": IMAGE_DIGEST,
        "official_image_digest_qualification": "Host-verified by the operator; this exporter checks original declarations and does not inspect Docker image identity itself.",
        "current_scripts": {"runner": source_record(args.runner), "analyzer": source_record(args.analyzer), "export_helper": source_record(Path(__file__))},
        "current_scripts_qualification": "Hashes read at export time; helper added after simulation. Original binary/patch hashes and commands remain in unchanged copied manifests.",
        "window_convention": "Exact half-open [start_ns,end_ns) intervals on receiver application delivery timestamps. A row at an event timestamp belongs to the post-event interval; packets sent before an event can arrive after it.",
        "metric": "Independent sum of payload_bytes from validated flow0/per-connection app trace, checked against full-analysis application total/goodput/bins. Includes startup for whole; Mbps=bytes*8/window_seconds/1e6.",
        "synthetic_event": "Micro event is at5s. The nominal step90to97ms name/after_ms48.5 manifest is retained, but MilliSeconds(uint64_t) makes actual one-way delay45→48ms and propagation RTT90→96ms (+6ms). Per-case source hashes and late wire latency corroborate the mismatch.",
        "leo_events": "Pre/post window names refer to121.6s/187.4s path events; throughput windows alone do not establish cause. Post121 starts10s after its event and post187 begins190s.",
        "original_data": "SHA256/byte inventory covers EVERY original regular run file, including full analysis and raw logs. Only compact summaries, original manifests and small LEO config/schedule are copied here.",
        "limitations": "Three deterministic screening cases, no confidence intervals, no improvement implemented, no eventual-delivery/drain control; synthetic two-node network differs from multi-hop LEO."})
    print(json.dumps({"out": str(args.out), "cases": len(cases), "windows": len(results), "validation": "passed"}))
    for row in results:
        print(f"{row['case']} {row['window']} [{row['start_s']},{row['end_s']}): {row['application_bytes']} B {row['application_goodput_mbps']:.9f} Mbps")


if __name__ == "__main__":
    main()
