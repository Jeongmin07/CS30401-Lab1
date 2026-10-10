"""Prepare compact, audited views of the existing v1 runs; run no simulations.

Use the untouched v1 raw archive as --raw-root. Receiver application delivery
is summed, not inferred from ACK progress. State traces are sampled as steps.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

NS = 1_000_000_000
CASES = ("v1-step-base", "v1-step-renew", "v1-leo-base", "v1-leo-renew")
FIELDS = ("case", "bin_start_ns", "bin_end_ns", "application_bytes",
          "application_goodput_mbps", "sample_time_ns", "cwnd_bytes",
          "socket_srtt_ns", "vegas_base_rtt_ns", "cycle_min_srtt_ns")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) ==
            (after.st_size, after.st_mtime_ns), f"Changed input: {path}")
    return {"bytes": before.st_size, "sha256": digest.hexdigest()}


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def official_step_trace(path, duration_ns):
    result = []
    previous = -1
    with path.open(newline="", encoding="utf-8") as stream:
        for flow, time, value in csv.reader(stream):
            require(flow == "0", f"Unexpected flow in {path}")
            time, value = int(time), int(value)
            require(previous <= time <= duration_ns, f"Invalid time in {path}")
            previous = time
            result.append((time, value))
    return result


def sample_steps(trace, boundaries):
    result = []
    index, current = 0, None
    for boundary in boundaries:
        while index < len(trace) and trace[index][0] <= boundary:
            current = trace[index][1]
            index += 1
        result.append(current)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path,
                        default=Path(__file__).resolve().parents[1] / "evidence")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    require(not any(args.out.iterdir()), "Choose an empty output directory")
    results = list(csv.DictReader((args.evidence / "results.csv").open(newline="")))
    all_series, segments, identities = [], [], {}
    for case in CASES:
        run = args.raw_root / case
        summary = json.loads((args.evidence / "cases" / case / "summary.json").read_text())
        original = {entry["relative_path"]: entry
                    for entry in summary["all_original_regular_files"]}
        manifest_identity = fingerprint(run / "case.json")
        require(manifest_identity == {key: original["case.json"][key]
                                      for key in ("bytes", "sha256")},
                f"Manifest differs from published v1 evidence: {case}")
        declared = json.loads((run / "case.json").read_text())
        duration_ns = int(declared["parameters"]["duration"]) * NS
        require(duration_ns == 200 * NS, f"Unexpected duration: {case}")
        app_logs = [relative for relative in original
                    if relative.startswith("logs_ns3/study_app_rx_node_") and relative.endswith(".csv")]
        require(len(app_logs) == 1, f"Expected one receiver app trace: {case}")
        names = (Path(app_logs[0]).name,
                 "tcp_flow_0_cwnd.csv", "tcp_flow_0_rtt.csv", "vegas_state.csv")
        input_hashes = {}
        for name in names:
            relative = "logs_ns3/" + name
            identity = fingerprint(run / relative)
            require(identity == {key: original[relative][key]
                                 for key in ("bytes", "sha256")},
                    f"Input differs from published v1 evidence: {case}/{relative}")
            input_hashes[relative] = identity
        boundaries = [index * NS for index in range(1, 201)]
        delivered = [0] * 200
        cuts = [0, 100 * NS, duration_ns] if "step" in case else \
               [0, 121_600_000_000, 187_400_000_000, duration_ns]
        segment_bytes = [0] * (len(cuts) - 1)
        previous, received_rows = -1, 0
        with (run / "logs_ns3" / names[0]).open(newline="") as stream:
            for row in csv.DictReader(stream):
                time = int(row["time_ns"])
                require(previous <= time < duration_ns, f"Invalid app time: {case}")
                require(row["flow_id"] == "0", f"Unexpected app flow: {case}")
                previous = time
                amount = int(row["payload_bytes"])
                require(amount > 0, f"Invalid payload: {case}")
                delivered[time // NS] += amount
                received_rows += 1
                for index, (start, end) in enumerate(zip(cuts, cuts[1:])):
                    if start <= time < end:
                        segment_bytes[index] += amount
                        break
        baseline = next(row for row in results if row["case"] == case and
                        row["window"] == "whole" and row["flow_id"] == "0")
        total = sum(delivered)
        require(total == int(baseline["application_bytes"]) == sum(segment_bytes),
                f"Delivery does not reconcile: {case}")
        require(abs(total * 8 / (duration_ns / NS) / 1e6 -
                    float(baseline["application_goodput_mbps"])) < 1e-9,
                f"Goodput does not reconcile: {case}")
        cwnd = sample_steps(official_step_trace(run / "logs_ns3" / names[1], duration_ns), boundaries)
        srtt = sample_steps(official_step_trace(run / "logs_ns3" / names[2], duration_ns), boundaries)
        bases, minima, previous = [], [], -1
        with (run / "logs_ns3" / names[3]).open(newline="") as stream:
            for row in csv.DictReader(stream):
                time = int(row["time_ns"])
                require(previous <= time <= duration_ns, f"Invalid state time: {case}")
                previous = time
                if row["vegas_instance"] != "1":
                    continue  # main_satnet also creates the peer's Vegas instance
                if row["base_rtt_ns"]:
                    bases.append((time, int(row["base_rtt_ns"])))
                if row["cycle_min_rtt_ns"]:
                    minima.append((time, int(row["cycle_min_rtt_ns"])))
        base = sample_steps(bases, boundaries)
        minimum = sample_steps(minima, boundaries)
        for index, end in enumerate(boundaries):
            all_series.append(dict(zip(FIELDS, (
                case, end - NS, end, delivered[index], delivered[index] * 8 / 1e6,
                end, cwnd[index], srtt[index], base[index], minimum[index]))))
        for index, (start, end) in enumerate(zip(cuts, cuts[1:])):
            segments.append({"case": case, "start_ns": start, "end_ns": end,
                             "application_bytes": segment_bytes[index],
                             "application_goodput_mbps": segment_bytes[index] * 8 /
                             ((end - start) / NS) / 1e6})
        identities[case] = {"simulation_commit": declared.get("source_commit"),
                            "simulation_manifest": manifest_identity,
                            "patch_sha256": declared["patch_sha256"],
                            "duration_ns": duration_ns,
                            "receiver_application_rows": received_rows,
                            "application_bytes": total, "inputs": input_hashes}
    write_csv(args.out / "timeseries.csv", FIELDS, all_series)
    write_csv(args.out / "segments.csv", tuple(segments[0]), segments)
    receipt = {"kind": "posthoc_view_of_existing_v1_runs", "no_new_simulations": True,
               "script": fingerprint(Path(__file__)),
               "input_results": fingerprint(args.evidence / "results.csv"),
               "application_windows": "[bin_start_ns, bin_end_ns), 1 second, flow 0",
               "trace_sampling": "last observed value at or before each sample_time_ns; no interpolation",
               "route_cut_interpretation": "temporal accounting, not causal attribution to a route event",
               "cases": identities,
               "outputs": {name: fingerprint(args.out / name)
                           for name in ("timeseries.csv", "segments.csv")}}
    (args.out / "preparation.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"cases": len(CASES), "bins": len(all_series),
                      "segments": len(segments), "all_input_hashes_and_delivery_totals_match": True}))


if __name__ == "__main__":
    main()
