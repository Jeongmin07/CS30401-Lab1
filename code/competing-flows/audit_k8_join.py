"""Compare retained join10 K20/K8 traces without running simulations.

The three declared GD/DG/GG pairs retain every measured row and field except
the threshold column and THRESHOLD_* control events. Those excluded controls
are validated separately against each actual schedule before comparison.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import audit_trajectory


PAIRS = tuple((f"join10-{mode}", f"join10-{mode}-k8") for mode in ("gd", "dg", "gg"))
WINDOWS = ((26_100_000_000, 26_500_000_000), (74_900_000_000, 75_300_000_000))
STARTS = (0, 10_000_000_000)
EXPECTED_CSVS = {
    "study_rx_node_1585_port_1024.csv", "study_app_rx_node_1585_port_1024.csv",
    "study_drops.csv", "study_drop_coverage.csv", "timing_results.csv",
    "tcp_flows.csv",
} | {f"tcp_flow_{fid}_{suffix}.csv" for fid in (0, 1) for suffix in (
    "cwnd", "rtt", "progress", "study_packets", "study_events")}
PROVENANCE_KEYS = ("patch_sha256", "binary_sha256", "runner_sha256",
                   "official_image", "official_image_digest", "make_run_sha256")
SIMULATION_PARAMETERS = ("rate", "queue", "duration", "start0_s", "start1_s", "state", "trace")
digest = audit_trajectory.digest


def fingerprint(path, relative_to):
    return {"path": str(path.relative_to(relative_to)), "bytes": path.stat().st_size,
            "sha256": digest(path)}


def guard_parameters(threshold):
    windows = "|".join(f"{start}:{end}" for start, end in WINDOWS)
    return f"study_threshold={threshold};study_windows={windows}"


def validate_threshold_events(path, fid, role, threshold):
    expected = [(STARTS[fid], "THRESHOLD_INIT", 3, 3)]
    if role == "G":
        for start, end in WINDOWS:
            expected.extend(((start, "THRESHOLD_SET", 3, threshold),
                             (end, "THRESHOLD_RESTORE", threshold, 3)))
    observed, evidence = [], []
    previous, current_k = -1, 3
    with path.open(newline="", encoding="utf-8") as source:
        for line, row in enumerate(csv.DictReader(source), 2):
            time_ns = int(row["time_ns"])
            if row["flow_id"] != str(fid) or not 0 <= time_ns < 200_000_000_000 or time_ns < previous:
                raise ValueError(f"Invalid event identity/time at {path}:{line}")
            previous = time_ns
            if row["event"].startswith("THRESHOLD_"):
                old, new = int(row["old_value"]), int(row["new_value"])
                if old != current_k:
                    raise ValueError(f"Threshold lifecycle has an inconsistent old K at {path}:{line}")
                current_k = new
                observed.append((time_ns, row["event"], old, new))
                evidence.append({"line": line, "time_ns": time_ns, "event": row["event"],
                                 "old_value": old, "new_value": new,
                                 "threshold": int(row["threshold"]), "cong_state": int(row["cong_state"])})
                if row["event"] == "THRESHOLD_RESTORE" and row["cong_state"] not in ("0", "4"):
                    raise ValueError(f"Threshold restored outside OPEN/LOSS at {path}:{line}")
            if int(row["threshold"]) != current_k:
                raise ValueError(f"Event threshold does not follow its lifecycle at {path}:{line}")
    if observed != expected or current_k != 3:
        raise ValueError(f"Actual threshold controls differ from the declared join10 schedule: {path}")
    return {"flow_id": fid, "role": role, "guard_k": threshold if role == "G" else None,
            "initial_k": 3, "final_k": current_k, "matched": True,
            "expected_lifecycle": [list(item) for item in expected], "observed_lifecycle": evidence}


def validate_run(run, mode, threshold):
    manifest_path = run / "case.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "complete" or manifest["exit_code"] != 0 or manifest["simulation_exit_code"] != 0:
        raise ValueError(f"Requires a successfully completed run: {run}")
    parameters = manifest["parameters"]
    if manifest["case"] != run.name or parameters["name"] != run.name or parameters["mode"] != mode:
        raise ValueError(f"Manifest name/mode disagrees with the declared case: {run}")
    expected_parameters = {"rate": 10, "queue": 100, "duration": 200,
                           "start0_s": 0, "start1_s": 10, "trace": 1}
    if any(parameters[key] != value for key, value in expected_parameters.items()):
        raise ValueError(f"Requires the declared 200s, 10Mbps, q100, join10 traced pair: {run}")
    if manifest["state"] != parameters["state"]:
        raise ValueError(f"Manifest state declarations disagree: {run}")

    config_path, schedule_path = run / "config_ns3.properties", run / "schedule.csv"
    actual_hashes = {"config_ns3.properties_sha256": digest(config_path),
                     "schedule.csv_sha256": digest(schedule_path)}
    if any(manifest[key] != value for key, value in actual_hashes.items()):
        raise ValueError(f"Actual config/schedule hash contradicts its manifest: {run}")
    with schedule_path.open(newline="", encoding="utf-8") as source:
        schedule = list(csv.reader(source))
    expected_schedule = [[str(fid), "1584", "1585", "100000000000", str(STARTS[fid]),
                          guard_parameters(threshold) if role == "G" else "", ""]
                         for fid, role in enumerate(mode)]
    if schedule != expected_schedule:
        raise ValueError(f"Actual schedule differs from the declared {mode}/K{threshold}: {run}")
    expected_flows = [{"flow_id": fid, "role": role, "source_node": 1584,
                       "destination_node": 1585, "size_bytes": 100000000000,
                       "start_ns": STARTS[fid], "additional_parameters": schedule[fid][5]}
                      for fid, role in enumerate(mode)]
    if manifest["flows"] != expected_flows:
        raise ValueError(f"Actual schedule and manifest flow declarations disagree: {run}")

    artifact_paths = {"patch_sha256": Path(parameters["patch"]),
                      "binary_sha256": Path(manifest["command"][0]),
                      "make_run_sha256": Path(manifest["setup_command"][1]),
                      "runner_sha256": Path(__file__).with_name("run_competing.py")}
    artifacts = {}
    for key, path in artifact_paths.items():
        actual = digest(path)
        if actual != manifest[key]:
            raise ValueError(f"Retained runtime artifact contradicts manifest {key}: {path}")
        artifacts[key] = {"path": str(path), "actual_sha256": actual, "manifest_matches": True}
    logs = run / "logs_ns3"
    inventory = {path.name for path in logs.glob("*.csv")}
    if inventory != EXPECTED_CSVS:
        raise ValueError(f"Expected the exact 16-CSV inventory at {run}; missing={EXPECTED_CSVS-inventory}, extra={inventory-EXPECTED_CSVS}")
    controls = [validate_threshold_events(logs / f"tcp_flow_{fid}_study_events.csv", fid, role, threshold)
                for fid, role in enumerate(mode)]
    inputs = [fingerprint(run / name, run) for name in ("case.json", "config_ns3.properties", "schedule.csv")]
    inputs.extend(fingerprint(logs / name, run) for name in sorted(inventory))
    return manifest, {"case": run.name, "run_dir": str(run), "guard_k": threshold,
                      "source_commit": manifest["source_commit"],
                      "actual_config_sha256": actual_hashes["config_ns3.properties_sha256"],
                      "actual_schedule_sha256": actual_hashes["schedule.csv_sha256"],
                      "verified_actual_runtime_artifacts": artifacts,
                      "threshold_schedule_validation": controls,
                      "raw_inputs": inputs}


def audit(root):
    comparisons, runs = [], {}
    for left_name, right_name in PAIRS:
        mode = left_name.rsplit("-", 1)[1].upper()
        left, right = root / left_name, root / right_name
        manifests = []
        for run, threshold in ((left, 20), (right, 8)):
            manifest, evidence = validate_run(run, mode, threshold)
            manifests.append(manifest)
            runs[run.name] = evidence
        for key in PROVENANCE_KEYS:
            if manifests[0][key] != manifests[1][key]:
                raise ValueError(f"Different provenance {key}: {left_name}/{right_name}")
        for key in SIMULATION_PARAMETERS:
            if manifests[0]["parameters"][key] != manifests[1]["parameters"][key]:
                raise ValueError(f"Different simulation parameter {key}: {left_name}/{right_name}")
        if runs[left_name]["actual_config_sha256"] != runs[right_name]["actual_config_sha256"]:
            raise ValueError(f"Actual configurations differ: {left_name}/{right_name}")
        files = [audit_trajectory.compare_file(left / "logs_ns3" / name, right / "logs_ns3" / name)
                 for name in sorted(EXPECTED_CSVS - audit_trajectory.EXCLUDED_FILES)]
        comparisons.append({"left": left_name, "right": right_name, "files_compared": len(files),
                            "source_commits": [manifest["source_commit"] for manifest in manifests],
                            "verified_equal_provenance": {key: manifests[0][key] for key in PROVENANCE_KEYS},
                            "actual_config_sha256": runs[left_name]["actual_config_sha256"],
                            "raw_equal_files": sum(item["raw_equal"] for item in files),
                            "normalized_equal_files": sum(item["normalized_equal"] for item in files),
                            "all_normalized_equal": all(item["normalized_equal"] for item in files),
                            "files": files})
    return {"schema_version": 1, "audit_script_sha256": digest(Path(__file__)),
            "comparison_helper": {"path": str(Path(audit_trajectory.__file__)),
                                  "sha256": digest(Path(audit_trajectory.__file__))},
            "root": str(root), "excluded_files": sorted(audit_trajectory.EXCLUDED_FILES),
            "normalization": "Reuse audit_trajectory.compare_file; ignore threshold column in named study traces and THRESHOLD_* sender control events only. Preserve every other row/field, UID, transmission tag and timestamp.",
            "excluded_control_validation": "Validate complete INIT/SET/RESTORE lifecycle, K and actual schedule for both flows before comparison; these declared join10 cases restore at their requested ends.",
            "runs": runs, "comparisons": comparisons,
            "all_pairs_normalized_equal": all(item["all_normalized_equal"] for item in comparisons),
            "limitations": [
                "Equality concerns the retained traced outputs of these three deterministic join10 K20/K8 pairs; no simulation or independent seed sample is generated.",
                "Equal traces do not expose every internal TCP decision, duplicate-ACK counter or SACK scoreboard state; they do not prove equal latent state or general threshold insensitivity.",
                "Wall-clock timing_results.csv is excluded from trajectory equality but its raw size and SHA are retained for every run.",
                "Image identity is a host-verified manifest declaration. Runtime artifact and config hashes are checked against retained files; the full external state tree is not rehashed.",
                "Source commits may differ while the verified runtime artifacts and simulation controls agree. This audit makes no fairness claim for other start orders, durations, queues or thresholds."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/tmp/cs30401-competing"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"Refusing to overwrite {args.out}")
    result = audit(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as target:
        target.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(args.out), "all_pairs_normalized_equal": result["all_pairs_normalized_equal"],
                      "pairs": [{key: comparison[key] for key in (
                          "left", "right", "files_compared", "raw_equal_files", "normalized_equal_files", "all_normalized_equal")}
                          for comparison in result["comparisons"]]}, indent=2))
    if not result["all_pairs_normalized_equal"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
