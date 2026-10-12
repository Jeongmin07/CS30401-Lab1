"""Inspect a bounded prefix of existing Hypatia forwarding updates, without simulation.

Forwarding files are incremental updates, not independent snapshots. All updates
up to a requested sample are applied, retaining only the selected destinations.
Only actual route walks and directed edge/egress overlap are reported. No queue,
capacity, geometric-delay, or congestion inference is made from route overlap.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import re
import time
from decimal import Decimal
from pathlib import Path

NS = 1_000_000_000
DEFAULT_TIMES = "0,20,40,60,100,140,180,199.9"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ns_seconds(value):
    scaled = Decimal(str(value)) * NS
    require(scaled.is_finite() and scaled >= 0 and scaled == int(scaled),
            f"Time must be a nonnegative whole number of nanoseconds: {value}")
    return int(scaled)


def write_csv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class BudgetStop(Exception):
    pass


class Reader:
    def __init__(self, args):
        self.args = args
        self.started = time.monotonic()
        self.bytes_read = 0
        self.rows_read = 0
        self.files_opened = 0
        self.metadata_bytes = 0
        self.inventory = []

    def elapsed(self):
        return time.monotonic() - self.started

    def check_time(self):
        if self.elapsed() > self.args.max_elapsed_s:
            raise BudgetStop("elapsed-time budget reached")

    def metadata(self, path):
        self.check_time()
        size = path.stat().st_size
        require(size <= self.args.max_metadata_bytes - self.metadata_bytes,
                f"Metadata byte budget exceeded: {path}")
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        require((before.st_size, before.st_mtime_ns) ==
                (after.st_size, after.st_mtime_ns), f"Changed metadata: {path}")
        self.metadata_bytes += len(data)
        return data, {"name": path.name, "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest()}

    def updates(self, path, destinations, total_nodes):
        self.check_time()
        if self.files_opened >= self.args.max_files:
            raise BudgetStop("forwarding-file budget reached")
        before = path.stat()
        if before.st_size > self.args.max_bytes - self.bytes_read:
            raise BudgetStop("forwarding-byte budget would be exceeded by the next file")
        self.files_opened += 1
        digest, updates = hashlib.sha256(), {}
        local_bytes, local_rows, selected_rows = 0, 0, 0
        entry = {"file": path.name, "declared_bytes": before.st_size,
                 "bytes_read": 0, "rows_read": 0, "selected_rows": 0,
                 "complete_file_sha256": "", "read_prefix_sha256": "",
                 "applied": False}
        try:
            with path.open("rb") as stream:
                while True:
                    self.check_time()
                    if self.rows_read >= self.args.max_rows:
                        raise BudgetStop("forwarding-row budget reached")
                    line = stream.readline(self.args.max_line_bytes + 1)
                    if not line:
                        break
                    digest.update(line)
                    local_bytes += len(line)
                    self.bytes_read += len(line)
                    local_rows += 1
                    self.rows_read += 1
                    require(len(line) <= self.args.max_line_bytes,
                            f"Oversized forwarding line in {path}")
                    # Do not convert or retain all source/destination rows.
                    prefix = line.rstrip(b"\r\n").split(b",", 2)
                    require(len(prefix) == 3, f"Invalid forwarding prefix in {path}")
                    if prefix[1] not in destinations:
                        continue
                    fields = line.rstrip(b"\r\n").split(b",")
                    require(len(fields) == 5, f"Expected five forwarding fields in {path}")
                    source, destination, next_hop, outgoing_if, incoming_if = map(int, fields)
                    require(0 <= source < total_nodes and 0 <= destination < total_nodes,
                            f"Node outside metadata range in {path}")
                    require(-1 <= next_hop < total_nodes, f"Invalid next hop in {path}")
                    if next_hop >= 0:
                        require(outgoing_if >= 0 and incoming_if >= 0,
                                f"Invalid interface indices in {path}")
                    key = (source, destination)
                    require(key not in updates, f"Duplicate selected update in {path}: {key}")
                    updates[key] = (next_hop, outgoing_if, incoming_if)
                    selected_rows += 1
            after = path.stat()
            require((before.st_size, before.st_mtime_ns) ==
                    (after.st_size, after.st_mtime_ns) and local_bytes == before.st_size,
                    f"Changed forwarding input: {path}")
            entry["complete_file_sha256"] = digest.hexdigest()
            entry["applied"] = True
            return updates
        finally:
            entry.update(bytes_read=local_bytes, rows_read=local_rows,
                         selected_rows=selected_rows)
            if not entry["applied"]:
                entry["read_prefix_sha256"] = digest.hexdigest()
            self.inventory.append(entry)


def route(pair, table, satellites, max_hops):
    current, destination = pair["source"], pair["destination"]
    nodes, edges, egresses = [current], [], []
    for _ in range(max_hops):
        if current == destination:
            return {"status": "reachable", "nodes": nodes, "edges": edges,
                    "egresses": egresses,
                    "isl_edges": [e for e in edges if e[0] < satellites and e[1] < satellites],
                    "gsl_edges": [e for e in edges if e[0] >= satellites or e[1] >= satellites]}
        update = table.get((current, destination))
        if update is None:
            status = "missing_forwarding_entry"
            break
        next_hop, outgoing_if, _ = update
        if next_hop < 0:
            status = "unreachable_next_hop"
            break
        if next_hop in nodes:
            status = "forwarding_loop"
            break
        edges.append((current, next_hop))
        egresses.append((current, outgoing_if))
        nodes.append(next_hop)
        current = next_hop
    else:
        status = "hop_budget_reached"
    return {"status": status, "nodes": nodes, "edges": [], "egresses": [],
            "isl_edges": [], "gsl_edges": []}


def overlap(first, second):
    valid = first["status"] == second["status"] == "reachable"
    def shared(key):
        return sorted(set(first[key]) & set(second[key])) if valid else []
    return {"both_reachable": valid, "shared_edges": shared("edges"),
            "shared_isl_edges": shared("isl_edges"), "shared_gsl_edges": shared("gsl_edges"),
            "shared_egresses": shared("egresses")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--dynamic", default="dynamic_state_100ms_for_200s")
    parser.add_argument("--pair", action="append", default=[],
                        help="label:source-node:destination-node; repeat for at most eight GS pairs")
    parser.add_argument("--samples-s", default=DEFAULT_TIMES)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-files", type=int, default=2000)
    parser.add_argument("--max-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--max-rows", type=int, default=2_000_000)
    parser.add_argument("--max-elapsed-s", type=float, default=30.0)
    parser.add_argument("--max-metadata-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--max-line-bytes", type=int, default=1024)
    parser.add_argument("--max-hops", type=int, default=64)
    args = parser.parse_args()
    for key in ("max_files", "max_bytes", "max_rows", "max_metadata_bytes", "max_line_bytes", "max_hops"):
        require(getattr(args, key) > 0, f"{key} must be positive")
    require(args.max_elapsed_s > 0, "max_elapsed_s must be positive")
    samples = sorted(set(ns_seconds(v.strip()) for v in args.samples_s.split(",")))
    require(1 <= len(samples) <= 8, "Choose one to eight sample times")
    require(not args.out.exists(), "Output directory must be new")
    reader = Reader(args)
    tle_data, tle_identity = reader.metadata(args.state / "tles.txt")
    constellation = list(map(int, tle_data.splitlines()[0].split()))
    require(len(constellation) == 2 and all(v > 0 for v in constellation), "Invalid TLE header")
    satellites = constellation[0] * constellation[1]
    require(len(tle_data.splitlines()) == 1 + 3 * satellites, "TLE satellite count does not reconcile")
    gs_data, gs_identity = reader.metadata(args.state / "ground_stations.txt")
    stations = {}
    for row in csv.reader(gs_data.decode("utf-8").splitlines()):
        require(len(row) == 8, "Expected eight extended ground-station fields")
        gid = int(row[0])
        require(gid not in stations, "Duplicate ground-station ID")
        stations[gid] = {"node_id": satellites + gid, "name": row[1],
                         "latitude": row[2], "longitude": row[3]}
    require(sorted(stations) == list(range(len(stations))), "Ground-station IDs must be consecutive")
    by_node = {s["node_id"]: s for s in stations.values()}
    require(len(stations) >= 2, "Need at least two ground stations")
    id_path = args.state / "node_ids.txt"
    metadata = [tle_identity, gs_identity]
    if id_path.exists():
        id_data, identity = reader.metadata(id_path)
        metadata.append(identity)
        id_rows = [r for r in csv.reader(id_data.decode("utf-8").splitlines()) if r and not r[0].startswith("#")]
        require({int(r[0]): r[1] for r in id_rows} == {n: s["name"] for n, s in by_node.items()},
                "node_ids.txt disagrees with ground-station metadata")
    pairs = []
    declarations = args.pair or [f"gs-{a}-to-{b}:{a}:{b}"
                                for a, b in itertools.permutations(sorted(by_node)[:4], 2)][:8]
    for declaration in declarations:
        label, source, destination = declaration.split(":")
        source, destination = int(source), int(destination)
        require(label and source != destination and source in by_node and destination in by_node,
                f"Pair must use distinct existing GS nodes: {declaration}")
        require(label not in {p["label"] for p in pairs}, "Duplicate pair label")
        pairs.append({"label": label, "source": source, "destination": destination,
                      "source_name": by_node[source]["name"], "destination_name": by_node[destination]["name"]})
    require(1 <= len(pairs) <= 8, "Choose one to eight pairs")
    dynamic = args.state / args.dynamic
    require(dynamic.is_dir(), "Dynamic-state directory missing")
    match = re.fullmatch(r"dynamic_state_(\d+)ms_for_(\d+)s", args.dynamic)
    require(match is not None, "Dynamic name must declare cadence and duration")
    step_ns, duration_ns = int(match[1]) * 1_000_000, int(match[2]) * NS
    require(step_ns > 0 and max(samples) < duration_ns and all(v % step_ns == 0 for v in samples),
            "Sample must lie on a forwarding step and before the state duration")
    destinations = {str(p["destination"]).encode("ascii") for p in pairs}
    combinations = list(itertools.combinations(range(len(pairs)), 2))
    profiles = {key: {"pair_a": pairs[key[0]]["label"], "pair_b": pairs[key[1]]["label"],
                     "four_distinct_endpoints": len({pairs[key[0]]["source"], pairs[key[0]]["destination"],
                                                     pairs[key[1]]["source"], pairs[key[1]]["destination"]}) == 4,
                     "same_endpoints": (pairs[key[0]]["source"], pairs[key[0]]["destination"]) ==
                                       (pairs[key[1]]["source"], pairs[key[1]]["destination"]),
                     "reverse_endpoints": (pairs[key[0]]["source"], pairs[key[0]]["destination"]) ==
                                          (pairs[key[1]]["destination"], pairs[key[1]]["source"]),
                     "states_evaluated": 0, "both_reachable_states": 0,
                     "isl_shared_states": 0, "isl_unshared_states": 0,
                     "gsl_shared_states": 0, "gsl_unshared_states": 0,
                     "overlap_changes": []} for key in combinations}
    table, previous_routes, previous_overlaps = {}, {}, {}
    samples_out, overlaps_out, changes = [], [], []
    stop_reason, last_applied = None, None
    try:
        for at in range(0, max(samples) + step_ns, step_ns):
            path = dynamic / f"fstate_{at}.txt"
            require(path.is_file(), f"Missing incremental update: {path}")
            updates = reader.updates(path, destinations, satellites + len(stations))
            table.update(updates)
            last_applied = at
            routes = [route(p, table, satellites, args.max_hops) for p in pairs]
            for index, current in enumerate(routes):
                if index in previous_routes and current != previous_routes[index]:
                    changes.append({"time_ns": at, "pair": pairs[index]["label"],
                                    "status": current["status"], "nodes": current["nodes"],
                                    "directed_egresses": current["egresses"]})
                if at in samples:
                    samples_out.append({"time_ns": at, "pair": pairs[index]["label"],
                        "source_node": pairs[index]["source"], "destination_node": pairs[index]["destination"],
                        "source_name": pairs[index]["source_name"], "destination_name": pairs[index]["destination_name"],
                        "status": current["status"], "forward_hops": len(current["edges"]),
                        "path_nodes": json.dumps(current["nodes"], separators=(",", ":")),
                        "directed_edges": json.dumps(current["edges"], separators=(",", ":")),
                        "directed_egresses": json.dumps(current["egresses"], separators=(",", ":"))})
                previous_routes[index] = current
            for key, profile in profiles.items():
                current = overlap(routes[key[0]], routes[key[1]])
                profile["states_evaluated"] += 1
                if current["both_reachable"]:
                    profile["both_reachable_states"] += 1
                    for kind in ("isl", "gsl"):
                        profile[f"{kind}_{'shared' if current[f'shared_{kind}_edges'] else 'unshared'}_states"] += 1
                if key in previous_overlaps and current != previous_overlaps[key]:
                    profile["overlap_changes"].append({"time_ns": at, **current})
                if at in samples:
                    overlaps_out.append({"time_ns": at, "pair_a": profile["pair_a"], "pair_b": profile["pair_b"],
                        "both_reachable": current["both_reachable"],
                        "shared_directed_edge_count": len(current["shared_edges"]),
                        "shared_isl_edge_count": len(current["shared_isl_edges"]),
                        "shared_gsl_edge_count": len(current["shared_gsl_edges"]),
                        "shared_directed_egress_count": len(current["shared_egresses"]),
                        "shared_isl_edges": json.dumps(current["shared_isl_edges"], separators=(",", ":")),
                        "shared_gsl_edges": json.dumps(current["shared_gsl_edges"], separators=(",", ":"))})
                previous_overlaps[key] = current
    except BudgetStop as exc:
        stop_reason = str(exc)
    for profile in profiles.values():
        profile["observed_isl_merge_split"] = bool(profile["isl_shared_states"] and profile["isl_unshared_states"])
        profile["gsl_overlap_at_every_reachable_state"] = bool(profile["both_reachable_states"] and
            profile["gsl_shared_states"] == profile["both_reachable_states"])
        profile["candidate_for_distinct_endpoint_isl_merge_split"] = bool(profile["observed_isl_merge_split"] and
            profile["four_distinct_endpoints"])
    args.out.mkdir(parents=True)
    write_csv(args.out / "path-samples.csv", ("time_ns", "pair", "source_node", "destination_node", "source_name",
        "destination_name", "status", "forward_hops", "path_nodes", "directed_edges", "directed_egresses"), samples_out)
    write_csv(args.out / "route-overlaps.csv", ("time_ns", "pair_a", "pair_b", "both_reachable",
        "shared_directed_edge_count", "shared_isl_edge_count", "shared_gsl_edge_count", "shared_directed_egress_count",
        "shared_isl_edges", "shared_gsl_edges"), overlaps_out)
    write_csv(args.out / "path-inputs.csv", ("file", "declared_bytes", "bytes_read", "rows_read", "selected_rows",
        "complete_file_sha256", "read_prefix_sha256", "applied"), reader.inventory)
    complete = stop_reason is None and last_applied == max(samples)
    candidates = [p for p in profiles.values() if p["candidate_for_distinct_endpoint_isl_merge_split"]]
    summary = {"kind": "bounded_existing_forwarding_prefix_probe", "no_simulation_or_state_generation": True,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "state_path": str(args.state), "dynamic_subdirectory": args.dynamic, "step_ns": step_ns,
        "state_duration_ns": duration_ns, "satellite_count": satellites, "ground_stations": list(stations.values()),
        "metadata_inputs": metadata, "pairs": pairs, "requested_samples_ns": samples,
        "completed_samples_ns": sorted({r["time_ns"] for r in samples_out}),
        "complete_requested_prefix": complete, "stop_reason": stop_reason,
        "last_applied_update_ns": last_applied, "route_changes": changes,
        "overlap_profiles": list(profiles.values()), "candidate_count": len(candidates),
        "endpoint_diversity_limit": "Only two GS nodes; repeated same-direction endpoints have identical routes, and opposite directions are not independent-endpoint data corridors."
            if len(stations) == 2 else None,
        "budgets": {k: getattr(args, k) for k in ("max_files", "max_bytes", "max_rows", "max_elapsed_s", "max_metadata_bytes", "max_line_bytes", "max_hops")},
        "read_cost": {"forwarding_files_opened": reader.files_opened,
            "forwarding_files_applied": sum(r["applied"] for r in reader.inventory),
            "forwarding_content_bytes_read": reader.bytes_read, "forwarding_rows_read": reader.rows_read,
            "selected_forwarding_rows": sum(r["selected_rows"] for r in reader.inventory),
            "metadata_content_bytes_read": reader.metadata_bytes,
            "total_input_content_bytes_read": reader.bytes_read + reader.metadata_bytes,
            "retained_selected_entries": len(table), "elapsed_s": reader.elapsed(),
            "meaning": "Logical input content bytes, including empty-file opens; not physical disk IO or simulator runtime. Elapsed limit is cooperatively checked before each read."},
        "limits": ["All prefix updates are applied; no sorting-based early exit or independent-snapshot assumption.",
            "Only selected destinations are retained, at most eight GS pairs and eight requested samples.",
            "Directed overlap is a necessary path condition, not proof of a shared queue or bottleneck.",
            "GSL overlap is reported separately; persistent endpoint sharing is not an intermittent ISL bottleneck.",
            "No geometric propagation delay, packet in-flight transition, queue occupancy, capacity, or TCP outcome is measured.",
            "A null result concerns only the declared nodes and completed time prefix; unfinished searches do not prove absence."],
        "outputs": {name: {"bytes": (args.out / name).stat().st_size,
            "sha256": hashlib.sha256((args.out / name).read_bytes()).hexdigest()}
            for name in ("path-samples.csv", "route-overlaps.csv", "path-inputs.csv")}}
    (args.out / "path-probe.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete_requested_prefix": complete, "candidate_count": len(candidates),
                      "ground_stations": len(stations), "read_cost": summary["read_cost"], "stop_reason": stop_reason}))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
